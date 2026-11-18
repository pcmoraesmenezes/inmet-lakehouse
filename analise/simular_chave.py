"""Simula a estação A502 ganhando uma versão nova e conta quantas chaves da dimensão trocam.

Compara a chave por posição na ordenação com a chave derivada de cod e ano_inicio, nos dados de MG.
Uso: python3 -m analise.simular_chave
"""
import sys

import pandas as pd

from analise.gabarito_ouro import estacoes_em_mg
from etl.dimensao import versionar

ESTACAO = "A502"
ANO_NOVO = 2026
DESLOCAMENTO_GRAUS = 0.02


def com_versao_nova(estacoes: pd.DataFrame) -> pd.DataFrame:
    nova = estacoes[estacoes.cod == ESTACAO].sort_values("ano").iloc[[-1]].assign(ano=ANO_NOVO)
    nova["lat"] = nova["lat"] + DESLOCAMENTO_GRAUS
    return pd.concat([estacoes, nova], ignore_index=True)


def chaves_trocadas(antes: pd.DataFrame, depois: pd.DataFrame, coluna: str) -> int:
    a = antes.set_index(["cod", "ano_inicio"])[coluna]
    d = depois.set_index(["cod", "ano_inicio"])[coluna]
    return int((a != d.reindex(a.index)).sum())


def main() -> None:
    estacoes = estacoes_em_mg()
    estacoes = estacoes[estacoes.em_mg]
    antes, depois = versionar(estacoes), versionar(com_versao_nova(estacoes))
    for dim in (antes, depois):
        dim["posicao"] = range(1, len(dim) + 1)
    print(f"{ESTACAO} com versão em {ANO_NOVO}: dimensão de {len(antes)} para {len(depois)} linhas")
    print(f"chave por posição:  {chaves_trocadas(antes, depois, 'posicao')} de {len(antes)} trocam")
    trocadas = chaves_trocadas(antes, depois, "estacao_sk")
    print(f"chave por cod e ano: {trocadas} de {len(antes)} trocam, chaves únicas: {depois.estacao_sk.is_unique}")
    sys.exit(1 if trocadas else 0)


if __name__ == "__main__":
    main()
