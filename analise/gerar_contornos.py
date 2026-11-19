"""Gera analise/uf_contornos.geojson: o contorno externo das 27 UFs, simplificado em 0,01 grau.

Fonte: Natural Earth 1:10m admin-1 (domínio público), arquivo ne_10m_admin_1_states_provinces.geojson.
Uso: python3 -m analise.gerar_contornos CAMINHO_DO_ARQUIVO_DO_NATURAL_EARTH
"""
import json
import math
import sys
from pathlib import Path

from analise.geo import distancia_ao_segmento

SAIDA = Path(__file__).resolve().parent / "uf_contornos.geojson"
TOLERANCIA_GRAUS = 0.01


def douglas_peucker(pontos: list[list[float]], tolerancia: float) -> list[list[float]]:
    manter = [False] * len(pontos)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pontos) - 1)]
    while pilha:
        ini, fim = pilha.pop()
        longe, indice = 0.0, None
        for i in range(ini + 1, fim):
            d = distancia_ao_segmento(pontos[i], pontos[ini], pontos[fim])
            if d > longe:
                longe, indice = d, i
        if indice is not None and longe > tolerancia:
            manter[indice] = True
            pilha += [(ini, indice), (indice, fim)]
    return [p for p, m in zip(pontos, manter) if m]


def simplificar_anel(anel: list[list[float]], tolerancia: float) -> list[list[float]]:
    # Um anel fechado tem extremos iguais; divide no ponto mais distante do início para a distância ao segmento fazer sentido.
    meio = max(range(len(anel)), key=lambda i: math.dist(anel[i], anel[0]))
    return douglas_peucker(anel[:meio + 1], tolerancia)[:-1] + douglas_peucker(anel[meio:], tolerancia)


def main(origem: str) -> None:
    dados = json.loads(Path(origem).read_text(encoding="utf-8"))
    ufs = []
    for f in dados["features"]:
        if f["properties"].get("iso_a2") != "BR":
            continue
        geometria = f["geometry"]
        poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
        aneis = [simplificar_anel(p[0], TOLERANCIA_GRAUS) for p in poligonos]
        ufs.append({"type": "Feature", "properties": {"uf": f["properties"]["postal"], "nome": f["properties"]["name"]},
                    "geometry": {"type": "MultiPolygon", "coordinates": [[a] for a in aneis if len(a) >= 4]}})
    colecao = {"type": "FeatureCollection", "fonte": "Natural Earth 1:10m admin-1 (dominio publico), simplificado em 0,01 grau",
               "features": sorted(ufs, key=lambda u: u["properties"]["uf"])}
    SAIDA.write_text(json.dumps(colecao, separators=(",", ":")), encoding="utf-8")
    print(f"{len(ufs)} UFs, {sum(len(a) for u in ufs for p in u['geometry']['coordinates'] for a in p)} pontos, "
          f"{SAIDA.stat().st_size} bytes")


if __name__ == "__main__":
    main(sys.argv[1])
