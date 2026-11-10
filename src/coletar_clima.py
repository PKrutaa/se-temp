"""Agrega células MERRA-2 por área de interseção com regiões oficiais da AESA."""
import argparse
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import shapefile
from shapely import box, make_valid, transform, union_all
from shapely.geometry import shape

GEO = "https://geoportal.aesa.pb.gov.br/assets/uploads/2025/05/"
API = "https://power.larc.nasa.gov/api/temporal/monthly/regional"
VARS = {"PRECTOTCORR": ("chuva_mm", "mm/day"), "T2M": ("temperatura_c", "C"),
        "EVPTRNS": ("et_fluxo_mj_m2_dia", "MJ/m^2/day")}


def baixar(url):
    with urlopen(url, timeout=90) as r:
        return r.read()


def geometrias(arquivo, campo):
    with ZipFile(BytesIO(baixar(GEO + arquivo))) as zip_file:
        get = lambda suf: zip_file.read(next(n for n in zip_file.namelist() if n.endswith(suf)))
        crs = CRS.from_wkt(get(".prj").decode())
        wgs = Transformer.from_crs(crs, 4326, always_xy=True)
        reader = shapefile.Reader(shp=BytesIO(get(".shp")), dbf=BytesIO(get(".dbf")), encoding="latin1")
        return [(r.record[campo].strip(), transform(make_valid(shape(r.shape.__geo_interface__)),
                                                   wgs.transform, interleaved=False))
                for r in reader.iterShapeRecords()]


def pesos_por_bacia(catalogo, pontos):
    formas = {}
    for arquivo, campo in (("Bacias-hidrograficas-da-paraiba.zip", "Nome"),
                           ("Sub_Bacias.zip", "Nome"), ("Regioes_dos_Rios.zip", "Regiao")):
        for nome, geometria in geometrias(arquivo, campo):
            formas.setdefault(nome, []).append(geometria)
    formas["Seridó"] = [*formas["Seridó Ocidental Paraibano"], *formas["Seridó Oriental Paraibano"]]
    area_proj = Transformer.from_crs(4326, 6933, always_xy=True)
    for registro in catalogo.itertuples(index=False):
        bacia = union_all(formas[registro.bacia])
        areas = []
        for lat, lon in pontos:
            pedaco = bacia.intersection(box(lon-.3125, lat-.25, lon+.3125, lat+.25))
            area = transform(pedaco, area_proj.transform, interleaved=False).area
            if area > 0:
                areas.append((registro.bacia_id, lat, lon, area))
        total = transform(bacia, area_proj.transform, interleaved=False).area
        if abs(sum(linha[-1] for linha in areas) / total - 1) > 0.002:
            raise ValueError(f"Cobertura incompleta para {registro.bacia}.")
        yield from areas


def consultar(parametro, cache):
    params = {"parameters": parametro, "community": "AG", "longitude-min": -39,
              "longitude-max": -34.5, "latitude-min": -8.5, "latitude-max": -5.75,
              "format": "JSON", "start": 2012, "end": 2026}
    arquivo = cache / f"nasa-{parametro}.json"
    if not arquivo.exists():
        arquivo.write_bytes(baixar(f"{API}?{urlencode(params)}"))
    dados = json.loads(arquivo.read_bytes())
    coluna, unidade = VARS[parametro]
    if dados["parameters"][parametro]["units"] != unidade:
        raise ValueError(f"Unidade inesperada para {parametro}.")
    falta = dados["header"]["fill_value"]
    linhas = []
    for celula in dados["features"]:
        lon, lat, *_ = celula["geometry"]["coordinates"]
        for codigo, valor in celula["properties"]["parameter"][parametro].items():
            if codigo.endswith("13"):
                continue
            mes = pd.Period(f"{codigo[:4]}-{codigo[4:]}", freq="M")
            if mes > pd.Period("2026-10", "M"):
                continue
            valor = np.nan if valor == falta else valor
            if parametro == "PRECTOTCORR":
                valor *= mes.days_in_month
            linhas.append((lat, lon, mes, valor))
    return pd.DataFrame(linhas, columns=["latitude_celula", "longitude_celula", "mes", coluna])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("../cache_nasa_power"))
    args = parser.parse_args()
    args.cache.mkdir(exist_ok=True, parents=True)
    base = pd.read_csv("data/acudes_mensal.csv")
    catalogo = base[["bacia_id", "bacia"]].dropna().drop_duplicates()
    chaves = ["latitude_celula", "longitude_celula", "mes"]
    clima = None
    for parametro in VARS:
        novo = consultar(parametro, args.cache)
        clima = novo if clima is None else clima.merge(novo, on=chaves, how="outer", validate="1:1")
    pontos = list(clima[chaves[:2]].drop_duplicates().itertuples(index=False, name=None))
    pesos = pd.DataFrame(pesos_por_bacia(catalogo, pontos),
                         columns=["bacia_id", *chaves[:2], "area_m2"])
    grade = pd.DataFrame({"mes": pd.period_range("2012-01", "2026-10", freq="M")})
    dados = pesos.merge(grade, how="cross").merge(clima, on=chaves, how="left", validate="m:1")
    dados["peso"] = dados.area_m2 / dados.groupby(["bacia_id", "mes"]).area_m2.transform("sum")
    colunas = [coluna for coluna, _ in VARS.values()]
    dados[colunas] = dados[colunas].mul(dados.peso, axis=0)
    grupos = dados.groupby(["bacia_id", "mes"])
    mensal = grupos[colunas].sum().where(grupos[colunas].count().eq(grupos.size(), axis=0))
    mensal.assign(celulas=grupos.size()).reset_index().to_csv("data/clima_bacias_mensal.csv", index=False)
    pesos.to_csv("data/clima_pesos_merra2.csv", index=False)
    print(f"{len(mensal)} linhas bacia/mês, cobertura {mensal.count().to_dict()}", flush=True)


if __name__ == "__main__":
    main()
