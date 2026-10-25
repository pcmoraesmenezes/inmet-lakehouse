"""Prata: tipa e conforma a bronze em silver_estacao_ano e silver_medicao, contando tudo o que descarta."""
import sys
from datetime import date, datetime
from functools import reduce
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(RAIZ))

import pandas as pd
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (BooleanType, DateType, DoubleType, IntegerType, StringType,
                               StructField, StructType)

from analise import geo
from etl.extrair import COD_NOME_DO_ARQUIVO
from etl.transformar import COLUNAS_MEDIDA, FORMATOS_FUNDACAO, escolher_formato

BRONZE = "workspace.inmet.bronze_csv"
ESTACAO = "workspace.inmet.silver_estacao_ano"
MEDICAO = "workspace.inmet.silver_medicao"
# Maximo de radiacao que chega ao topo da atmosfera em uma hora: 1361 W/m2 por 3600 s.
LIMITE_RADIACAO_KJM2 = 5000
LINHA_DE_DADO = F.col("c00").rlike(r"^\d{4}[-/]\d{2}[-/]\d{2}$")
ESQUEMA_ESTACAO = StructType([
    StructField("cod", StringType()), StructField("nome", StringType()), StructField("uf", StringType()),
    StructField("regiao", StringType()), StructField("lat", DoubleType()), StructField("lon", DoubleType()),
    StructField("alt", DoubleType()), StructField("data_fundacao", DateType()), StructField("em_mg", BooleanType()),
    StructField("ano", IntegerType()), StructField("arquivo", StringType()),
])

spark = SparkSession.builder.getOrCreate()
# Hora do arquivo e UTC: com outro fuso de sessao o timestamp guardado deslocaria.
spark.conf.set("spark.sql.session.timeZone", "UTC")


def numero(coluna: str) -> str:
    return f"try_cast(nullif(nullif(regexp_replace({coluna}, ',', '.'), '-9999'), '') AS double)"


def sem_medida(coluna: str):
    return F.coalesce(F.col(coluna), F.lit("")).isin("", "-9999")


def data_de_fundacao(texto: str | None) -> date | None:
    try:
        return datetime.strptime(texto, escolher_formato(texto, FORMATOS_FUNDACAO)).date()
    except (TypeError, ValueError):
        return None


def nativo(valor):
    valor = valor.item() if hasattr(valor, "item") else valor
    return None if valor is None or (isinstance(valor, float) and valor != valor) else valor


def estacao_ano() -> pd.DataFrame:
    def do_cabecalho(prefixo: str, nome: str):
        return F.max(F.when(F.col("c00").startswith(prefixo), F.col("c01"))).alias(nome)

    df = (spark.table(BRONZE).filter(~LINHA_DE_DADO).groupBy("arquivo", "ano")
          .agg(do_cabecalho("REGI", "regiao"), do_cabecalho("UF", "uf"), do_cabecalho("LATITUDE", "lat"),
               do_cabecalho("LONGITUDE", "lon"), do_cabecalho("ALTITUDE", "alt"),
               do_cabecalho("DATA DE FUNDA", "fundacao"))
          .toPandas())
    for coluna in ("lat", "lon", "alt"):
        df[coluna] = pd.to_numeric(df[coluna].str.replace(",", "."), errors="coerce")
    aneis = geo.carregar_contorno()
    df["data_fundacao"] = df.fundacao.map(data_de_fundacao)
    df["em_mg"] = [bool(pd.notna(la) and pd.notna(lo) and geo.dentro(lo, la, aneis)) for la, lo in zip(df.lat, df.lon)]
    df = df.join(df.arquivo.str.extract(COD_NOME_DO_ARQUIVO))
    return df[["cod", "nome", "uf", "regiao", "lat", "lon", "alt", "data_fundacao", "em_mg", "ano", "arquivo"]]


def gravar_estacoes() -> None:
    linhas = [tuple(nativo(v) for v in r) for r in estacao_ano().itertuples(index=False)]
    (spark.createDataFrame(linhas, schema=ESQUEMA_ESTACAO).write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable(ESTACAO))


def conferir_estacoes() -> bool:
    tabela = spark.table(ESTACAO)
    arquivos = spark.table(BRONZE).select("arquivo").distinct().count()
    n, sem_fundacao = tabela.count(), tabela.filter(F.col("data_fundacao").isNull()).count()
    fora = tabela.filter(~F.col("em_mg")).select("cod", "nome", "ano", "lat", "lon").orderBy("cod", "ano")
    ok = n == arquivos and sem_fundacao == 0
    print(f"estacao_ano: {n} linhas para {arquivos} arquivos, {sem_fundacao} sem data de fundacao, "
          f"{fora.count()} linhas com em_mg falso, {'OK' if ok else 'DIVERGE'}")
    fora.show(truncate=False)
    return ok


def criar_tabela_medicao() -> None:
    medidas = ", ".join(f"{c} DOUBLE" for c in COLUNAS_MEDIDA)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {MEDICAO} "
              f"(cod STRING, data_hora_utc TIMESTAMP, {medidas}, arquivo STRING, ano INT) USING DELTA")


def preparar(ano: int):
    quando = F.coalesce(
        F.expr("try_to_timestamp(concat(c00, ' ', c01), 'yyyy-MM-dd HH:mm')"),
        F.expr("try_to_timestamp(concat(c00, ' ', substring(c01, 1, 4)), 'yyyy/MM/dd HHmm')"),
    )
    medidas = [F.expr(numero(f"c{i:02d}")).alias(nome) for i, nome in zip(range(2, 19), COLUNAS_MEDIDA)]
    return (spark.table(BRONZE).filter((F.col("ano") == ano) & LINHA_DE_DADO)
            .select(F.regexp_extract("arquivo", r"_MG_([A-Z]\d+)_", 1).alias("cod"), quando.alias("data_hora_utc"),
                    *medidas, "arquivo", "ano"))


def carregar_ano(ano: int) -> int:
    preparado = preparar(ano)
    sem_data = preparado.filter(F.col("data_hora_utc").isNull()).count()
    if sem_data:
        raise ValueError(f"{ano}: {sem_data} linhas sem data e hora legivel")
    anuladas = preparado.filter(F.col("radiacao_kjm2") > LIMITE_RADIACAO_KJM2).count()
    limpo = preparado.withColumn(
        "radiacao_kjm2", F.when(F.col("radiacao_kjm2") > LIMITE_RADIACAO_KJM2, F.lit(None)).otherwise(F.col("radiacao_kjm2")))
    alguma_medida = reduce(lambda a, b: a | b, [F.col(c).isNotNull() for c in COLUNAS_MEDIDA])
    (limpo.filter(alguma_medida).write.format("delta").mode("overwrite")
     .option("replaceWhere", f"ano = {ano}").saveAsTable(MEDICAO))
    return anuladas


def conferir_ano(ano: int, anuladas: int) -> bool:
    bronze = spark.table(BRONZE).filter((F.col("ano") == ano) & LINHA_DE_DADO)
    prata = spark.table(MEDICAO).filter(F.col("ano") == ano)
    na_bronze, na_prata = bronze.count(), prata.count()
    descartadas = na_bronze - na_prata
    duplicadas = prata.groupBy("cod", "data_hora_utc").count().filter("count > 1").count()
    ausentes = bronze.agg(*[F.sum(F.when(sem_medida(f"c{i:02d}"), 1).otherwise(0)).alias(nome)
                            for i, nome in zip(range(2, 19), COLUNAS_MEDIDA)]).first()
    nulos = prata.agg(*[F.sum(F.when(F.col(nome).isNull(), 1).otherwise(0)).alias(nome)
                        for nome in COLUNAS_MEDIDA]).first()
    # Linha descartada tem todas as medidas ausentes, entao cada medida (fora a radiacao, que tambem anula o excesso) fecha a conta.
    contas = all(ausentes[n] == nulos[n] + descartadas for n in COLUNAS_MEDIDA if n != "radiacao_kjm2")
    ok = contas and duplicadas == 0
    print(f"{ano}: bronze {na_bronze}, prata {na_prata}, descartadas {descartadas}, radiacao anulada {anuladas}, "
          f"duplicadas {duplicadas}, contas das medidas {'OK' if contas else 'DIVERGEM'}")
    return ok


def main() -> None:
    gravar_estacoes()
    resultados = [conferir_estacoes()]
    criar_tabela_medicao()
    for ano in sorted(r.ano for r in spark.table(BRONZE).select("ano").distinct().collect()):
        resultados.append(conferir_ano(ano, carregar_ano(ano)))
    print(f"\nsilver_medicao: {spark.table(MEDICAO).count()} linhas")
    if not all(resultados):
        raise SystemExit("a prata nao fecha com a bronze em algum ponto")


if __name__ == "__main__":
    main()
