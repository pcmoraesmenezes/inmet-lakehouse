"""Contorno de MG, ponto dentro do contorno e distancia entre coordenadas, so com a biblioteca padrao."""
import json
import math
from pathlib import Path

CONTORNO = Path(__file__).resolve().parent / "mg_contorno.geojson"
RAIO_TERRA_KM = 6371.0


def carregar_contorno() -> list[list[tuple[float, float]]]:
    geometria = json.loads(CONTORNO.read_text(encoding="utf-8"))["features"][0]["geometry"]
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    return [[tuple(p) for p in poligono[0]] for poligono in poligonos]


def dentro(lon: float, lat: float, aneis: list[list[tuple[float, float]]]) -> bool:
    return any(_dentro_do_anel(lon, lat, anel) for anel in aneis)


def _dentro_do_anel(lon: float, lat: float, anel: list[tuple[float, float]]) -> bool:
    cruzamentos = 0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            cruzamentos += 1
    return cruzamentos % 2 == 1


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))
