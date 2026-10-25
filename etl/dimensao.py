"""Versiona as estacoes: uma versao nova so quando a posicao ou a altitude mudam alem do arredondamento."""
import pandas as pd

from analise import geo

LIMITE_POSICAO_M = 100
LIMITE_ALTITUDE_M = 10


def nativo(valor):
    valor = valor.item() if hasattr(valor, "item") else valor
    return None if valor is None or (isinstance(valor, float) and valor != valor) else valor


def mudou(referencia, atual) -> bool:
    posicao_m = 1000 * geo.distancia_km(referencia.lat, referencia.lon, atual.lat, atual.lon)
    altitude_mudou = (pd.notna(referencia.alt) and pd.notna(atual.alt)
                      and abs(referencia.alt - atual.alt) > LIMITE_ALTITUDE_M)
    return posicao_m > LIMITE_POSICAO_M or altitude_mudou


def versionar(estacoes: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for cod, grupo in estacoes.sort_values("ano").groupby("cod"):
        versoes: list[dict] = []
        for registro in grupo.itertuples():
            if versoes and not mudou(versoes[-1]["referencia"], registro):
                versoes[-1].update(ano_fim=registro.ano, registro=registro)
            else:
                versoes.append(dict(ano_inicio=registro.ano, ano_fim=registro.ano, referencia=registro, registro=registro))
        ultimo = grupo.iloc[-1]
        for i, v in enumerate(versoes):
            r = v["registro"]
            linhas.append(dict(cod=cod, nome=ultimo.nome, uf=ultimo.uf, regiao=ultimo.regiao, lat=r.lat, lon=r.lon,
                               alt=r.alt, data_fundacao=ultimo.data_fundacao, ano_inicio=int(v["ano_inicio"]),
                               ano_fim=int(v["ano_fim"]), atual=i == len(versoes) - 1))
    dimensao = pd.DataFrame(linhas).sort_values(["cod", "ano_inicio"]).reset_index(drop=True)
    dimensao.insert(0, "estacao_sk", range(1, len(dimensao) + 1))
    return dimensao
