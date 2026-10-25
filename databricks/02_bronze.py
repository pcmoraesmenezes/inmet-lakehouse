"""Bronze: carrega todas as linhas dos CSV de MG do volume numa tabela Delta, sem converter nada."""
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType

CSV_DIR = "/Volumes/workspace/inmet/raw/zips/csv_mg"
TABELA = "workspace.inmet.bronze_csv"
COLUNAS = [f"c{i:02d}" for i in range(20)]
SCHEMA = StructType([StructField(c, StringType(), True) for c in COLUNAS])
# Valor que nunca aparece nos dados: sem ele o leitor trata campo vazio como nulo e a bronze perderia a diferenca entre vazio e ausente.
SENTINELA_NULO = "__sem_valor__"

spark = SparkSession.builder.getOrCreate()


def criar_tabela() -> None:
    colunas = ", ".join(f"{c} STRING" for c in COLUNAS)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {TABELA} "
              f"(arquivo STRING, ano INT, ingestao_em TIMESTAMP, {colunas}) USING DELTA")


def ler_ano(ano: int):
    leitura = (
        spark.read.schema(SCHEMA)
        .option("sep", ";")
        .option("encoding", "ISO-8859-1")
        .option("nullValue", SENTINELA_NULO)
        .csv(f"{CSV_DIR}/{ano}/*.CSV")
    )
    return leitura.select(
        F.element_at(F.split(F.col("_metadata.file_path"), "/"), -1).alias("arquivo"),
        F.lit(ano).alias("ano"),
        F.current_timestamp().alias("ingestao_em"),
        *COLUNAS,
    )


def carregar_ano(ano: int) -> None:
    (ler_ano(ano).write.format("delta").mode("overwrite")
     .option("replaceWhere", f"ano = {ano}").saveAsTable(TABELA))


def conferir_ano(ano: int) -> bool:
    nos_csv = (spark.read.text(f"{CSV_DIR}/{ano}/*.CSV")
               .filter(F.length(F.trim("value")) > 0).count())
    tabela = spark.table(TABELA).filter(F.col("ano") == ano)
    na_bronze, arquivos = tabela.count(), tabela.select("arquivo").distinct().count()
    ok = na_bronze == nos_csv
    print(f"{ano}: {na_bronze} linhas na bronze, {nos_csv} nos CSV, {arquivos} arquivos, {'OK' if ok else 'DIVERGE'}")
    return ok


def mostrar_cabecalhos() -> None:
    print("\ncabecalhos como vieram, por ano:")
    (spark.table(TABELA).filter(F.col("c00").isin("DATA (YYYY-MM-DD)", "Data"))
     .groupBy("ano", "c00", "c01").count().orderBy("ano").show(truncate=False))


def main() -> None:
    criar_tabela()
    anos = sorted(int(p.name) for p in Path(CSV_DIR).iterdir() if p.is_dir())
    resultados = []
    for ano in anos:
        carregar_ano(ano)
        resultados.append(conferir_ano(ano))
    mostrar_cabecalhos()
    if not all(resultados):
        raise SystemExit("a bronze diverge dos CSV em algum ano")


if __name__ == "__main__":
    main()
