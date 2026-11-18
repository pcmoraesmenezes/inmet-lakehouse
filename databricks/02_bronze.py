"""Bronze nacional: carrega todas as linhas dos CSV do Brasil, ano a ano, numa tabela Delta, sem converter nada."""
import json
import shutil
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType

from analise import gabarito_bronze_br
from ingest import extrair_zip

RAW = "/Volumes/workspace/inmet/raw"
CSV_DIR = f"{RAW}/zips/csv_br"
TABELA = "workspace.inmet.bronze_br"
ANOS = None
UF = None
COLUNAS = [f"c{i:02d}" for i in range(20)]
SCHEMA = StructType([StructField(c, StringType(), True) for c in COLUNAS])
# Valor que nunca aparece nos dados: sem ele o leitor trata campo vazio como nulo e a bronze perderia a diferenca entre vazio e ausente.
SENTINELA_NULO = "__sem_valor__"

spark = SparkSession.builder.getOrCreate()


def criar_tabela() -> None:
    colunas = ", ".join(f"{c} STRING" for c in COLUNAS)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {TABELA} "
              f"(arquivo STRING, uf STRING, ano INT, ingestao_em TIMESTAMP, {colunas}) USING DELTA")


def ler_ano(ano: int):
    leitura = (
        spark.read.schema(SCHEMA)
        .option("sep", ";")
        .option("encoding", "ISO-8859-1")
        .option("nullValue", SENTINELA_NULO)
        .csv(f"{CSV_DIR}/{ano}/*.CSV")
    )
    arquivo = F.element_at(F.split(F.col("_metadata.file_path"), "/"), -1)
    return leitura.select(
        arquivo.alias("arquivo"),
        F.regexp_extract(arquivo, r"^INMET_[A-Z]+_([A-Z]{2})_", 1).alias("uf"),
        F.lit(ano).alias("ano"),
        F.current_timestamp().alias("ingestao_em"),
        *COLUNAS,
    )


def carregar_ano(ano: int) -> None:
    (ler_ano(ano).write.format("delta").mode("overwrite")
     .option("replaceWhere", f"ano = {ano}").saveAsTable(TABELA))


def esperado(gabarito: dict, ano: int) -> tuple[int, int]:
    g = gabarito[str(ano)]
    if UF is None:
        return g["linhas"], g["por_uf"]["MG"]["linhas"]
    return g["por_uf"][UF]["linhas"], g["por_uf"][UF]["linhas"] if UF == "MG" else 0


def conferir_ano(ano: int, gabarito: dict) -> bool:
    nos_csv = (spark.read.text(f"{CSV_DIR}/{ano}/*.CSV")
               .filter(F.length(F.trim("value")) > 0).count())
    tabela = spark.table(TABELA).filter(F.col("ano") == ano)
    na_bronze, arquivos = tabela.count(), tabela.select("arquivo").distinct().count()
    em_mg = tabela.filter(F.col("uf") == "MG").count()
    nos_zips, mg_nos_zips = esperado(gabarito, ano)
    ok = na_bronze == nos_csv == nos_zips and em_mg == mg_nos_zips
    print(f"{ano}: {na_bronze} linhas na bronze, {nos_csv} nos CSV, {nos_zips} nos zips, {arquivos} arquivos, "
          f"MG {em_mg} contra {mg_nos_zips}, {'OK' if ok else 'DIVERGE'}")
    return ok


def mostrar_cabecalhos(anos: list[int]) -> None:
    print("\ncabecalhos como vieram, por ano:")
    (spark.table(TABELA).filter(F.col("ano").isin(anos) & F.col("c00").isin("DATA (YYYY-MM-DD)", "Data"))
     .groupBy("ano", "c00", "c01").count().orderBy("ano").show(truncate=False))


def main() -> None:
    criar_tabela()
    manifesto = extrair_zip.ler_manifesto(Path(RAW))
    gabarito = json.loads(gabarito_bronze_br.SAIDA.read_text(encoding="utf-8"))
    anos = ANOS or sorted(manifesto)
    resultados = []
    for ano in anos:
        extrair_zip.extrair_ano(Path(RAW), ano, manifesto[ano], Path(CSV_DIR), UF)
        carregar_ano(ano)
        ok = conferir_ano(ano, gabarito)
        resultados.append(ok)
        if ok:
            shutil.rmtree(f"{CSV_DIR}/{ano}")
    mostrar_cabecalhos(anos)
    if not all(resultados):
        raise SystemExit("a bronze diverge dos CSV ou dos zips em algum ano")


if __name__ == "__main__":
    main()
