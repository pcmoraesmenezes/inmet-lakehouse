"""Gabarito da ouro calculado dos CSV locais: linhas da dimensao e do fato por ano, para comparar com o Databricks."""
import numpy as np
import pandas as pd

from analise import geo
from etl import dimensao
from etl.extrair import COD_NOME_DO_ARQUIVO, CSV_MG, ler_bruto
from etl.transformar import COLUNAS_MEDIDA, decimal

LIMITE_RADIACAO_KJM2 = 5000


def estacoes_em_mg() -> pd.DataFrame:
    aneis = geo.carregar_contorno()
    linhas = []
    for pasta in sorted(CSV_MG.iterdir()):
        for arq in sorted(pasta.glob("*.CSV")):
            regiao, uf, _, _, lat, lon, alt, _ = ler_bruto(arq)[0]
            nome = COD_NOME_DO_ARQUIVO.fullmatch(arq.name)
            lat, lon = decimal(lat), decimal(lon)
            em_mg = lat is not None and lon is not None and geo.dentro(lon, lat, aneis)
            linhas.append(dict(cod=nome["cod"], ano=int(pasta.name), nome=nome["nome"], uf=uf, regiao=regiao, lat=lat,
                               lon=lon, alt=decimal(alt), data_fundacao=None, em_mg=em_mg, arquivo=arq))
    return pd.DataFrame(linhas)


def linhas_da_prata(arquivo) -> int:
    df = pd.read_csv(arquivo, sep=";", skiprows=9, header=None, dtype=str, encoding="latin-1",
                     keep_default_na=False, usecols=range(2, 19))
    df.columns = COLUNAS_MEDIDA
    numeros = df.mask(df.isin(["", "-9999"])).apply(lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce"))
    numeros.loc[numeros["radiacao_kjm2"] > LIMITE_RADIACAO_KJM2, "radiacao_kjm2"] = np.nan
    return int(numeros.notna().any(axis=1).sum())


def main() -> None:
    est = estacoes_em_mg()
    dim = dimensao.versionar(est[est.em_mg])
    versoes = dim.groupby("cod").size()
    print(f"gold_dim_estacao: {len(dim)} linhas, {dim.cod.nunique()} estacoes, {int((versoes > 1).sum())} com mais de uma versao "
          f"(limites {dimensao.LIMITE_POSICAO_M} m e {dimensao.LIMITE_ALTITUDE_M} m)")
    por_ano = est[est.em_mg].groupby("ano").arquivo.apply(lambda arqs: sum(linhas_da_prata(a) for a in arqs))
    print("fato esperado por ano:", {int(a): int(n) for a, n in por_ano.items()}, "| total:", int(por_ano.sum()))


if __name__ == "__main__":
    main()
