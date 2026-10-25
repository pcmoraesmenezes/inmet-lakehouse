"""Analise da bronze: cinco degraus, cada um com uma pergunta, uma figura e uma frase-resposta."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(RAIZ))

import pandas as pd
from pyspark.sql import SparkSession, functions as F

from analise import figuras

TABELA = "workspace.inmet.bronze_csv"
SAIDA = Path("/Volumes/workspace/inmet/raw/analise")
LINHA_DE_DADO = F.col("c00").rlike(r"^\d{4}[-/]\d{2}[-/]\d{2}$")
HORA_UTC = F.regexp_extract("c01", r"(\d{2})", 1).cast("int")

spark = SparkSession.builder.getOrCreate()


def numero(coluna: str) -> str:
    return f"try_cast(nullif(nullif(regexp_replace({coluna}, ',', '.'), '-9999'), '') AS double)"


def dados() -> "pyspark.sql.DataFrame":
    return spark.table(TABELA).filter(LINHA_DE_DADO)


def estacoes() -> pd.DataFrame:
    def do_cabecalho(prefixo: str, nome: str):
        return F.max(F.when(F.col("c00").startswith(prefixo), F.col("c01"))).alias(nome)

    df = (spark.table(TABELA).filter(~LINHA_DE_DADO).groupBy("arquivo", "ano")
          .agg(do_cabecalho("LATITUDE", "lat"), do_cabecalho("LONGITUDE", "lon"), do_cabecalho("ALTITUDE", "alt"))
          .toPandas())
    for coluna in ("lat", "lon", "alt"):
        df[coluna] = pd.to_numeric(df[coluna].str.replace(",", "."), errors="coerce")
    return df.join(df.arquivo.str.extract(figuras.COD_NOME_DO_ARQUIVO))


def ausentes() -> pd.DataFrame:
    base = dados().withColumn("hora", HORA_UTC)
    de_dia = F.col("hora").between(*figuras.HORA_DIA_UTC)
    de_noite = (F.col("hora") >= figuras.HORA_NOITE_UTC[0]) | (F.col("hora") <= figuras.HORA_NOITE_UTC[1])

    def sem_medida(coluna: str):
        return F.coalesce(F.col(coluna), F.lit("")).isin("", "-9999")

    def conta(condicao, nome: str):
        return F.sum(F.when(condicao, 1).otherwise(0)).alias(nome)

    expressoes = [F.count(F.lit(1)).alias("linhas"), conta(de_dia, "dia"), conta(de_noite, "noite"),
                  conta(de_dia & sem_medida("c06"), "rad_dia"), conta(de_noite & sem_medida("c06"), "rad_noite")]
    expressoes += [conta(sem_medida(c), c) for c in figuras.MEDIDAS]
    linhas = []
    for r in base.groupBy("ano").agg(*expressoes).toPandas().to_dict("records"):
        for c in figuras.MEDIDAS:
            if c == "c06":
                linhas.append(dict(ano=r["ano"], variavel="c06", linhas=r["dia"], ausentes=r["rad_dia"]))
                linhas.append(dict(ano=r["ano"], variavel="c06n", linhas=r["noite"], ausentes=r["rad_noite"]))
            else:
                linhas.append(dict(ano=r["ano"], variavel=c, linhas=r["linhas"], ausentes=r[c]))
    return pd.DataFrame(linhas)


def faixas() -> pd.DataFrame:
    expressoes = []
    for c in figuras.MEDIDAS:
        n = numero(c)
        expressoes += [F.expr(f"min({n})").alias(f"{c}_min"), F.expr(f"max({n})").alias(f"{c}_max"),
                       F.expr(f"percentile_approx({n}, array(0.01, 0.5, 0.99))").alias(f"{c}_q")]
    linhas = []
    for r in dados().groupBy("ano").agg(*expressoes).toPandas().to_dict("records"):
        for c in figuras.MEDIDAS:
            q = r[f"{c}_q"]
            p01, mediana, p99 = (q[0], q[1], q[2]) if q is not None and len(q) == 3 else (float("nan"),) * 3
            linhas.append(dict(ano=r["ano"], variavel=c, minimo=r[f"{c}_min"], p01=p01, mediana=mediana,
                               p99=p99, maximo=r[f"{c}_max"]))
    return pd.DataFrame(linhas)


def temperatura(est: pd.DataFrame) -> pd.DataFrame:
    n = numero("c07")
    df = (dados().filter(F.col("ano") == int(est.ano.max())).groupBy("arquivo", "ano")
          .agg(F.expr(f"avg({n})").alias("temp_media"), F.expr(f"count({n}) / count(1)").alias("cobertura"))
          .toPandas())
    return df.merge(est[["arquivo", "cod", "alt"]], on="arquivo")


def ficha(est: pd.DataFrame) -> None:
    total = spark.table(TABELA).count()
    print(f"bronze: {figuras.milhar(total)} linhas, {est.arquivo.nunique()} arquivos de estação e ano, "
          f"{est.cod.nunique()} estações, {int(est.ano.min())} a {int(est.ano.max())}")


def main(degraus: list[int]) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    est = estacoes()
    ficha(est)

    def arquivo(nome: str) -> str:
        return str(SAIDA / nome)

    if 1 in degraus:
        print("1.", figuras.figura_posicoes(est, arquivo("1_posicoes.png")))
    if 2 in degraus:
        print("2.", figuras.figura_deslocamentos(est, arquivo("2_deslocamentos.png")))
    if 3 in degraus:
        quadro = ausentes()
        print("gabarito, % das celulas sem medida nas 16 medidas fora a radiacao:", figuras.gabarito_ausentes(quadro))
        print("3.", figuras.figura_ausentes(quadro, arquivo("3_ausentes.png")))
    if 4 in degraus:
        print("4.", figuras.figura_valores_tipicos(faixas(), arquivo("4_valores_tipicos.png")))
    if 5 in degraus:
        print("5.", figuras.figura_altitude_temperatura(temperatura(est), arquivo("5_altitude_temperatura.png")))


if __name__ == "__main__":
    escolhidos = [int(a) for a in sys.argv[1:] if a.isdigit() and 1 <= int(a) <= 5]
    main(escolhidos or [1, 2, 3, 4, 5])
