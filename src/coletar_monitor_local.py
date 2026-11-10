"""Extrai a classe do Monitor no ponto de cadastro de cada açude."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import shapefile
from shapely import intersects_xy, make_valid
from shapely.errors import GEOSException
from shapely.geometry import shape

from coletar_clima import baixar

CATALOGO = ("https://apimsbr.ana.gov.br/rest/cms-msne/mapa-monitor?final=true&response_format=apil5"
            "&use_fk=true&include_all_obj_fk=true&limit=200&orderBy=id,desc")
ARQUIVOS = "https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/"
CLASSES = {"si": -1, **{f"s{i}": i for i in range(5)}}


def camada_seca(z):
    por_nome = {n.casefold(): n for n in z.namelist()}
    candidatas = []
    for chave in por_nome:
        if not chave.endswith(".shp") or any(s in chave for s in ("impacto", "cortado")):
            continue
        stem = chave[:-4]
        arquivos = [por_nome.get(stem + e) for e in (".shp", ".dbf", ".prj")]
        if not all(arquivos):
            continue
        shp, dbf, prj = arquivos
        try:
            r = shapefile.Reader(shp=BytesIO(z.read(shp)), dbf=BytesIO(z.read(dbf)), encoding="latin1")
        except (KeyError, shapefile.ShapefileException):
            continue
        campos = {f[0].lower(): f[0] for f in r.fields[1:]}
        campo = next((campos[x] for x in ("uf_codigo", "categoria", "classe", "ind") if x in campos), None)
        if campo is None:
            continue
        codigos = {str(reg[campo]).strip().lower() for reg in r.iterRecords()}
        if not codigos or not codigos.issubset(CLASSES):
            continue
        candidatas.append(("isolado" not in chave, -len(codigos), len(chave), shp, r, campo, z.read(prj)))
    if not candidatas:
        raise ValueError("Sem camada reconhecida de severidade.")
    return min(candidatas, key=lambda t: t[:3])[3:]


def categorizar(item, catalogo, cache):
    mes = f"{item['ano']}-{item['mes']:02}"
    valores = np.full(len(catalogo), -9)
    camada, falha = None, None
    try:
        caminho = item["shape"][0]["path"]
        arquivo = cache / f"{mes}.zip"
        if not arquivo.exists():
            arquivo.write_bytes(baixar(ARQUIVOS + quote(caminho, safe="/")))
        with ZipFile(arquivo) as z:
            camada, r, campo, wkt = camada_seca(z)
            crs = CRS.from_wkt(wkt.decode("latin1"))
            tr = Transformer.from_crs(4326, crs, always_xy=True)
            x, y = tr.transform(catalogo.longitude.to_numpy(), catalogo.latitude.to_numpy())
            for sr in r.iterShapeRecords():
                if not hasattr(sr.shape, "bbox"):
                    continue
                xmin, ymin, xmax, ymax = sr.shape.bbox
                indices = np.flatnonzero((x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax))
                if not len(indices):
                    continue
                codigo = CLASSES[str(sr.record[campo]).strip().lower()]
                geom = make_valid(shape(sr.shape.__geo_interface__))
                dentro = indices[intersects_xy(geom, x[indices], y[indices])]
                valores[dentro] = np.maximum(valores[dentro], codigo)
    except (URLError, TimeoutError, BadZipFile, ValueError, IndexError, KeyError, shapefile.ShapefileException, GEOSException) as e:
        falha = f"{type(e).__name__}: {e}"
        valores[:] = -9
    return (
        pd.DataFrame({"mes": mes, "acude_id": catalogo.acude_id, "monitor_local_severidade":
                      pd.Series(valores).where(valores != -9).astype("Int64")}),
        {"mes": mes, "mapa_id": item["id"], "camada": camada,
         "classificados": int((valores != -9).sum()), "falha": falha},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("../cache_monitor"))
    args = parser.parse_args()
    args.cache.mkdir(exist_ok=True, parents=True)
    indice = json.loads(baixar(CATALOGO))["data"]["list"]
    indice = [i for i in indice if (2012, 1) <= (i["ano"], i["mes"]) <= (2026, 10)]
    catalogo = pd.read_csv("data/acudes_mensal.csv")[["acude_id", "latitude", "longitude"]]
    catalogo = catalogo.drop_duplicates("acude_id").reset_index(drop=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        resultados = list(pool.map(lambda item: categorizar(item, catalogo, args.cache), indice))
    pd.concat([d for d, _ in resultados], ignore_index=True).sort_values(["mes", "acude_id"]).to_csv(
        "data/monitor_local_mensal.csv", index=False
    )
    qualidade = pd.DataFrame([r for _, r in resultados]).sort_values("mes")
    qualidade.to_csv("data/monitor_local_auditoria.csv", index=False)
    print(qualidade.classificados.describe().to_string(), flush=True)
    print(qualidade[qualidade.falha.notna()].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
