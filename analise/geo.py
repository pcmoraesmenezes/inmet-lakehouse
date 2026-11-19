"""Contornos das UFs, ponto dentro do contorno e distancia entre coordenadas, so com a biblioteca padrao."""
import json
import math
from pathlib import Path

CONTORNO = Path(__file__).resolve().parent / "mg_contorno.geojson"
CONTORNOS = Path(__file__).resolve().parent / "uf_contornos.geojson"
RAIO_TERRA_KM = 6371.0
KM_POR_GRAU = 111.195
TOLERANCIA_FRONTEIRA_KM = 10


def carregar_contorno() -> list[list[tuple[float, float]]]:
    geometria = json.loads(CONTORNO.read_text(encoding="utf-8"))["features"][0]["geometry"]
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    return [[tuple(p) for p in poligono[0]] for poligono in poligonos]


def carregar_contornos() -> dict[str, list[list[tuple[float, float]]]]:
    features = json.loads(CONTORNOS.read_text(encoding="utf-8"))["features"]
    return {f["properties"]["uf"]: [[tuple(p) for p in poligono[0]] for poligono in f["geometry"]["coordinates"]]
            for f in features}


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


def distancia_ao_segmento(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def distancia_a_fronteira_km(lon: float, lat: float, aneis: list[list[tuple[float, float]]]) -> float:
    escala = math.cos(math.radians(lat))
    ponto = (lon * escala, lat)
    graus = min(distancia_ao_segmento(ponto, (x1 * escala, y1), (x2 * escala, y2))
                for anel in aneis for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1]))
    return graus * KM_POR_GRAU


def na_uf(lon: float, lat: float, aneis: list[list[tuple[float, float]]]) -> bool:
    # O contorno simplificado e a costa de 1:10m deixam estação litorânea ou de divisa alguns km fora do polígono.
    return dentro(lon, lat, aneis) or distancia_a_fronteira_km(lon, lat, aneis) <= TOLERANCIA_FRONTEIRA_KM
