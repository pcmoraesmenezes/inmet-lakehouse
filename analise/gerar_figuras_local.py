"""Mesma analise da bronze, calculada com pandas sobre os CSV locais, para testar as figuras e gerar o gabarito."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analise import figuras
from etl.extrair import CSV_MG, ler_bruto
from etl.transformar import decimal

SAIDA = CSV_MG.parent / "figuras_local"
COLUNAS_MEDIDA = figuras.MEDIDAS


def estacoes() -> pd.DataFrame:
    linhas = []
    for pasta in sorted(CSV_MG.iterdir()):
        for arq in sorted(pasta.glob("*.CSV")):
            _, _, _, _, lat, lon, alt, _ = ler_bruto(arq)[0]
            nome_do_arquivo = figuras.COD_NOME_DO_ARQUIVO.fullmatch(arq.name)
            linhas.append(dict(arquivo=arq.name, ano=int(pasta.name), cod=nome_do_arquivo["cod"], nome=nome_do_arquivo["nome"],
                               lat=decimal(lat), lon=decimal(lon), alt=decimal(alt)))
    return pd.DataFrame(linhas)


def ler_medidas(arq: Path) -> pd.DataFrame:
    return pd.read_csv(arq, sep=";", skiprows=9, header=None, dtype=str, encoding="latin-1",
                       keep_default_na=False, usecols=range(1, 19))


def numerico(coluna: pd.Series) -> pd.Series:
    return pd.to_numeric(coluna.mask(coluna.isin(["", "-9999"])).str.replace(",", "."), errors="coerce")


def agregados() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ausentes, faixas, temp = [], [], []
    for pasta in sorted(CSV_MG.iterdir()):
        ano = int(pasta.name)
        valores = {c: [] for c in COLUNAS_MEDIDA}
        linhas, falta = 0, np.zeros(len(COLUNAS_MEDIDA), dtype=int)
        dia, noite, rad_dia, rad_noite = 0, 0, 0, 0
        for arq in sorted(pasta.glob("*.CSV")):
            df = ler_medidas(arq)
            hora = df.pop(1).str.extract(r"(\d{2})")[0].astype(int)
            de_dia = hora.between(*figuras.HORA_DIA_UTC).to_numpy()
            de_noite = ((hora >= figuras.HORA_NOITE_UTC[0]) | (hora <= figuras.HORA_NOITE_UTC[1])).to_numpy()
            df.columns = COLUNAS_MEDIDA
            linhas += len(df)
            falta += df.isin(["", "-9999"]).sum().to_numpy()
            sem_radiacao = df["c06"].isin(["", "-9999"]).to_numpy()
            dia += int(de_dia.sum())
            noite += int(de_noite.sum())
            rad_dia += int((sem_radiacao & de_dia).sum())
            rad_noite += int((sem_radiacao & de_noite).sum())
            numeros = {c: numerico(df[c]) for c in COLUNAS_MEDIDA}
            for c in COLUNAS_MEDIDA:
                valores[c].append(numeros[c].dropna().to_numpy())
            t = numeros["c07"]
            temp.append(dict(arquivo=arq.name, ano=ano, temp_media=t.mean(), cobertura=t.notna().mean()))
        for c, f in zip(COLUNAS_MEDIDA, falta):
            if c == "c06":
                ausentes.append(dict(ano=ano, variavel="c06", linhas=dia, ausentes=rad_dia))
                ausentes.append(dict(ano=ano, variavel="c06n", linhas=noite, ausentes=rad_noite))
            else:
                ausentes.append(dict(ano=ano, variavel=c, linhas=linhas, ausentes=int(f)))
            v = np.concatenate(valores[c])
            if v.size == 0:
                print(f"sem nenhum valor valido: {figuras.NOMES[c]} em {ano}")
                faixas.append(dict(ano=ano, variavel=c, minimo=np.nan, p01=np.nan, mediana=np.nan, p99=np.nan, maximo=np.nan))
                continue
            p01, mediana, p99 = np.quantile(v, [0.01, 0.5, 0.99])
            faixas.append(dict(ano=ano, variavel=c, minimo=v.min(), p01=p01, mediana=mediana, p99=p99, maximo=v.max()))
    return pd.DataFrame(ausentes), pd.DataFrame(faixas), pd.DataFrame(temp)


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    est = estacoes()
    ausentes, faixas, temp = agregados()
    temp = temp.merge(est[["arquivo", "cod", "alt"]], on="arquivo")
    print("gabarito, % das celulas sem medida nas 16 medidas fora a radiacao:", figuras.gabarito_ausentes(ausentes))
    print("1.", figuras.figura_posicoes(est, str(SAIDA / "1_posicoes.png")))
    print("2.", figuras.figura_deslocamentos(est, str(SAIDA / "2_deslocamentos.png")))
    print("3.", figuras.figura_ausentes(ausentes, str(SAIDA / "3_ausentes.png")))
    print("4.", figuras.figura_valores_tipicos(faixas, str(SAIDA / "4_valores_tipicos.png")))
    print("5.", figuras.figura_altitude_temperatura(temp, str(SAIDA / "5_altitude_temperatura.png")))
    faixas.to_csv(SAIDA / "faixas.csv", index=False)


if __name__ == "__main__":
    sys.exit(main())
