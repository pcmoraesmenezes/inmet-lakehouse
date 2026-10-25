"""Ouro: estrela de Kimball do clima de MG, com estacao versionada, calendario, hora e o fato por estacao e hora."""
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(RAIZ))

import pandas as pd
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (BooleanType, DateType, DoubleType, IntegerType, LongType, StringType,
                               StructField, StructType)

from etl.dimensao import nativo, versionar
from etl.transformar import COLUNAS_MEDIDA, DESLOCAMENTO_LOCAL_H, periodo_do_dia

ESTACAO_ANO = "workspace.inmet.silver_estacao_ano"
MEDICAO = "workspace.inmet.silver_medicao"
DIM_ESTACAO = "workspace.inmet.gold_dim_estacao"
DIM_DATA = "workspace.inmet.gold_dim_data"
DIM_HORA = "workspace.inmet.gold_dim_hora"
FATO = "workspace.inmet.gold_fato_medicao_hora"
DIAS_DA_SEMANA = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo"]

ESQUEMA_DIM_ESTACAO = StructType([
    StructField("estacao_sk", LongType()), StructField("cod", StringType()), StructField("nome", StringType()),
    StructField("uf", StringType()), StructField("regiao", StringType()), StructField("lat", DoubleType()),
    StructField("lon", DoubleType()), StructField("alt", DoubleType()), StructField("data_fundacao", DateType()),
    StructField("ano_inicio", IntegerType()), StructField("ano_fim", IntegerType()), StructField("atual", BooleanType()),
])
ESQUEMA_DIM_DATA = StructType([
    StructField("data_sk", IntegerType()), StructField("data", DateType()), StructField("ano", IntegerType()),
    StructField("trimestre", IntegerType()), StructField("mes", IntegerType()), StructField("dia", IntegerType()),
    StructField("dia_da_semana", StringType()), StructField("fim_de_semana", BooleanType()),
])
ESQUEMA_DIM_HORA = StructType([
    StructField("hora_utc", IntegerType()), StructField("hora_local", IntegerType()), StructField("periodo", StringType()),
])

spark = SparkSession.builder.getOrCreate()
# data_sk e hora_utc saem do timestamp: com outro fuso de sessao a data mudaria.
spark.conf.set("spark.sql.session.timeZone", "UTC")


def gravar_dimensao(quadro: pd.DataFrame, esquema: StructType, tabela: str) -> None:
    linhas = [tuple(nativo(v) for v in r) for r in quadro[[c.name for c in esquema]].itertuples(index=False)]
    (spark.createDataFrame(linhas, schema=esquema).write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable(tabela))


def montar_dim_estacao() -> pd.DataFrame:
    estacoes = spark.table(ESTACAO_ANO).filter("em_mg").toPandas()
    dimensao = versionar(estacoes)
    for cod, anos in estacoes.groupby("cod").ano:
        janelas = dimensao[dimensao.cod == cod]
        cobertos = {a for j in janelas.itertuples() for a in range(j.ano_inicio, j.ano_fim + 1)}
        if not set(anos) <= cobertos:
            raise ValueError(f"{cod}: as versoes nao cobrem todos os anos da estacao")
    return dimensao


def montar_dim_data() -> pd.DataFrame:
    primeiro, ultimo = spark.table(MEDICAO).agg(F.min("ano"), F.max("ano")).first()
    dias = pd.date_range(date(primeiro, 1, 1), date(ultimo, 12, 31)).date
    return pd.DataFrame({
        "data_sk": [d.year * 10000 + d.month * 100 + d.day for d in dias], "data": dias,
        "ano": [d.year for d in dias], "trimestre": [(d.month - 1) // 3 + 1 for d in dias],
        "mes": [d.month for d in dias], "dia": [d.day for d in dias],
        "dia_da_semana": [DIAS_DA_SEMANA[d.weekday()] for d in dias], "fim_de_semana": [d.weekday() >= 5 for d in dias],
    })


def montar_dim_hora() -> pd.DataFrame:
    horas = range(24)
    return pd.DataFrame({"hora_utc": horas, "hora_local": [(h + DESLOCAMENTO_LOCAL_H) % 24 for h in horas],
                         "periodo": [periodo_do_dia(h) for h in horas]})


def criar_tabela_fato() -> None:
    medidas = ", ".join(f"{c} DOUBLE" for c in COLUNAS_MEDIDA)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {FATO} (estacao_sk BIGINT, data_sk INT, hora_utc INT, "
              f"data_hora_utc TIMESTAMP, {medidas}, ano INT) USING DELTA")


def carregar_fato(ano: int) -> None:
    silver = spark.table(MEDICAO).filter(F.col("ano") == ano).alias("s")
    dimensao = F.broadcast(spark.table(DIM_ESTACAO).select("estacao_sk", "cod", "ano_inicio", "ano_fim")).alias("d")
    junta = (F.col("s.cod") == F.col("d.cod")) & F.col("s.ano").between(F.col("d.ano_inicio"), F.col("d.ano_fim"))
    fato = silver.join(dimensao, junta).select(
        F.col("d.estacao_sk").alias("estacao_sk"),
        F.date_format("s.data_hora_utc", "yyyyMMdd").cast("int").alias("data_sk"),
        F.hour("s.data_hora_utc").alias("hora_utc"),
        F.col("s.data_hora_utc").alias("data_hora_utc"),
        *[F.col(f"s.{c}") for c in COLUNAS_MEDIDA],
        F.col("s.ano").alias("ano"),
    )
    (fato.write.format("delta").mode("overwrite").option("replaceWhere", f"ano = {ano}").saveAsTable(FATO))


def conferir_ano(ano: int) -> bool:
    cods = spark.table(DIM_ESTACAO).select("cod").distinct()
    silver = spark.table(MEDICAO).filter(F.col("ano") == ano).join(cods, "cod")
    fato = spark.table(FATO).filter(F.col("ano") == ano)
    na_prata, no_fato = silver.count(), fato.count()
    duplicadas = fato.groupBy("estacao_sk", "data_hora_utc").count().filter("count > 1").count()
    sem_data = fato.join(spark.table(DIM_DATA), "data_sk", "left_anti").count()
    sem_hora = fato.join(spark.table(DIM_HORA), "hora_utc", "left_anti").count()
    contar = [F.count(c).alias(c) for c in COLUNAS_MEDIDA]
    medidas_iguais = silver.agg(*contar).first() == fato.agg(*contar).first()
    ok = na_prata == no_fato and duplicadas == 0 and sem_data == 0 and sem_hora == 0 and medidas_iguais
    print(f"{ano}: prata em MG {na_prata}, fato {no_fato}, duplicadas {duplicadas}, sem data {sem_data}, "
          f"sem hora {sem_hora}, contagens das medidas {'OK' if medidas_iguais else 'DIFEREM'}")
    return ok


def main() -> None:
    dim_estacao = montar_dim_estacao()
    gravar_dimensao(dim_estacao, ESQUEMA_DIM_ESTACAO, DIM_ESTACAO)
    gravar_dimensao(montar_dim_data(), ESQUEMA_DIM_DATA, DIM_DATA)
    gravar_dimensao(montar_dim_hora(), ESQUEMA_DIM_HORA, DIM_HORA)
    versionadas = dim_estacao.groupby("cod").size()
    print(f"gold_dim_estacao: {len(dim_estacao)} linhas, {dim_estacao.cod.nunique()} estacoes, "
          f"{int((versionadas > 1).sum())} com mais de uma versao")
    print(f"gold_dim_data: {spark.table(DIM_DATA).count()} dias | gold_dim_hora: {spark.table(DIM_HORA).count()} horas")
    criar_tabela_fato()
    anos = sorted(r.ano for r in spark.table(MEDICAO).select("ano").distinct().collect())
    resultados = []
    for ano in anos:
        carregar_fato(ano)
        resultados.append(conferir_ano(ano))
    print(f"\ngold_fato_medicao_hora: {spark.table(FATO).count()} linhas")
    if not all(resultados):
        raise SystemExit("a ouro nao fecha com a prata em algum ano")


if __name__ == "__main__":
    main()
