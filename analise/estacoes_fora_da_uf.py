"""Lista as estações-ano cuja coordenada fica fora da UF declarada no próprio arquivo, com a tolerância de fronteira.

Uso: python3 -m analise.estacoes_fora_da_uf
"""
from collections import defaultdict

from analise import geo
from etl.extrair import cabecalhos_do_zip
from etl.transformar import decimal

ANOS = range(2016, 2026)


def fora_da_uf() -> dict[tuple[str, str, str], list[tuple[int, float | None]]]:
    contornos = geo.carregar_contornos()
    fora = defaultdict(list)
    for ano in ANOS:
        for _, (_, uf, nome, cod, lat, lon, _, _) in cabecalhos_do_zip(ano):
            lat, lon = decimal(lat), decimal(lon)
            if lat is None or lon is None:
                fora[(uf, cod, nome)].append((ano, None))
            elif not geo.na_uf(lon, lat, contornos[uf]):
                fora[(uf, cod, nome)].append((ano, geo.distancia_a_fronteira_km(lon, lat, contornos[uf])))
    return fora


def main() -> None:
    fora = fora_da_uf()
    for (uf, cod, nome), anos in sorted(fora.items()):
        distancias = [d for _, d in anos if d is not None]
        distancia = f"{max(distancias):.0f} km" if distancias else "sem coordenada"
        print(f"{uf} {cod} {nome}: {len(anos)} ano(s), até {distancia} da fronteira")
    print(f"{len(fora)} estações, {sum(len(a) for a in fora.values())} estações-ano fora da UF com tolerância de {geo.TOLERANCIA_FRONTEIRA_KM} km")


if __name__ == "__main__":
    main()
