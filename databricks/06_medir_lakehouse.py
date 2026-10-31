"""Mede o lakehouse com as mesmas provas de analise/medir_dw.py e analise/medir_schema.py, numa copia descartavel da fato."""
import threading
import time

from pyspark.sql import SparkSession, functions as F

FATO = "workspace.inmet.gold_fato_medicao_hora"
DIM_ESTACAO = "workspace.inmet.gold_dim_estacao"
MEDICAO = "workspace.inmet.silver_medicao"
COPIA = "workspace.inmet.gold_fato_teste"
ANO, ESTACAO, DIA = 2025, "A502", "2025-03-15"
REPETICOES = 3
ESPERA_LEITOR_S = 1.0

spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")


def cronometrar(funcao) -> tuple[object, float]:
    inicio = time.perf_counter()
    resultado = funcao()
    return resultado, time.perf_counter() - inicio


def medir(rotulo: str, sql: str) -> float:
    inicio = time.perf_counter()
    try:
        spark.sql(sql).collect()
        resultado = f"{time.perf_counter() - inicio:.2f} s"
    except Exception as erro:
        resultado = f"falhou em {time.perf_counter() - inicio:.2f} s: {str(erro).splitlines()[0][:160]}"
    print(f"{rotulo}: {resultado}")
    return time.perf_counter() - inicio


def tamanho(tabela: str) -> str:
    d = spark.sql(f"DESCRIBE DETAIL {tabela}").first()
    return f"{d.sizeInBytes / 1024 ** 2:.0f} MB em {d.numFiles} arquivos"


def consulta_do_dia(tabela: str, estacao_sk: int | None = None) -> list[float]:
    filtro = f"data_hora_utc >= '{DIA}' AND data_hora_utc < date_add('{DIA}', 1)"
    if estacao_sk is not None:
        filtro += f" AND estacao_sk = {estacao_sk}"
    return [cronometrar(lambda: spark.sql(f"SELECT count(*) FROM {tabela} WHERE {filtro}").collect())[1]
            for _ in range(REPETICOES)]


def formatar(tempos: list[float]) -> str:
    return ", ".join(f"{t:.2f} s" for t in tempos)


def reprocessar_estacao(estacao_sk: int) -> int:
    spark.sql(f"DELETE FROM {COPIA} WHERE estacao_sk = {estacao_sk} AND ano = {ANO}")
    novas = spark.sql(f"SELECT * FROM {FATO} WHERE estacao_sk = {estacao_sk} AND ano = {ANO}")
    novas.write.format("delta").mode("append").saveAsTable(COPIA)
    return novas.count()


def reprocessar_ano() -> int:
    """A menor unidade do pipeline de verdade: um ano inteiro, trocado por replaceWhere."""
    ano = spark.table(FATO).filter(F.col("ano") == ANO)
    ano.write.format("delta").mode("overwrite").option("replaceWhere", f"ano = {ANO}").saveAsTable(COPIA)
    return ano.count()


def troca_de_tipo_com_leitor(estacao_sk: int) -> None:
    espera: list[float] = []

    def leitor() -> None:
        time.sleep(ESPERA_LEITOR_S)
        espera.append(cronometrar(lambda: spark.sql(f"SELECT count(*) FROM {COPIA} WHERE estacao_sk = {estacao_sk}").collect())[1])

    fio = threading.Thread(target=leitor)
    fio.start()
    medir("ALTER COLUMN pressao_mb TYPE float, caminho nativo (estreitar o tipo)",
          f"ALTER TABLE {COPIA} ALTER COLUMN pressao_mb TYPE float")
    _, reescrita = cronometrar(lambda: spark.table(COPIA).withColumn("pressao_mb", F.col("pressao_mb").cast("float"))
                               .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(COPIA))
    fio.join()
    print(f"ALTER COLUMN pressao_mb TYPE float, reescrevendo a tabela com cast: {reescrita:.2f} s")
    print(f"  consulta de 1 estacao feita 1 s depois do inicio esperou {espera[0]:.2f} s")


def main() -> None:
    sk = spark.sql(f"SELECT estacao_sk FROM {DIM_ESTACAO} WHERE cod = '{ESTACAO}' AND {ANO} BETWEEN ano_inicio AND ano_fim").first().estacao_sk
    linhas = spark.table(FATO).count()
    print(f"fato: {linhas} linhas, {tamanho(FATO)}, ano {ANO}, estacao {ESTACAO} (estacao_sk {sk}), dia {DIA}")

    spark.sql(f"DROP TABLE IF EXISTS {COPIA}")
    try:
        medir("copiar a fato para a tabela de teste (DEEP CLONE)", f"CREATE TABLE {COPIA} DEEP CLONE {FATO}")
        print(f"tamanho da copia: {tamanho(COPIA)}")

        print(f"consulta de 1 dia, todas as estacoes: {formatar(consulta_do_dia(COPIA))} (a 1a inclui a partida)")
        print(f"consulta de 1 dia, 1 estacao: {formatar(consulta_do_dia(COPIA, sk))}")

        gravadas, t = cronometrar(lambda: reprocessar_estacao(sk))
        print(f"reprocessar {ESTACAO} de {ANO} (DELETE e append): {gravadas} linhas, {t:.2f} s")
        gravadas, t = cronometrar(reprocessar_ano)
        print(f"reprocessar o ano {ANO} inteiro por replaceWhere (a menor unidade do pipeline): {gravadas} linhas, {t:.2f} s")

        inicio = time.perf_counter()
        spark.sql(f"DELETE FROM {COPIA} WHERE estacao_sk = {sk} AND data_hora_utc >= '{DIA}' AND data_hora_utc < date_add('{DIA}', 1)")
        print(f"DELETE de 1 dia da {ESTACAO}: {(time.perf_counter() - inicio) * 1000:.0f} ms")
        spark.sql(f"RESTORE TABLE {COPIA} TO VERSION AS OF 0").collect()

        medir("ADD COLUMN sensor_novo float (anula as linhas antigas)", f"ALTER TABLE {COPIA} ADD COLUMN sensor_novo float")
        medir("ADD COLUMN flag smallint NOT NULL DEFAULT 0", f"ALTER TABLE {COPIA} ADD COLUMN flag smallint NOT NULL DEFAULT 0")
        troca_de_tipo_com_leitor(sk)
        medir("ADD CONSTRAINT CHECK (precip_mm >= 0) validando as linhas",
              f"ALTER TABLE {COPIA} ADD CONSTRAINT precip_nao_negativa CHECK (precip_mm >= 0)")
        antes = tamanho(COPIA)
        medir("UPDATE sensor_novo = 0 em todas as linhas (preencher o historico)", f"UPDATE {COPIA} SET sensor_novo = 0")
        print(f"tamanho antes e depois do UPDATE: {antes} e {tamanho(COPIA)}")
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {COPIA}")
    print(f"copia removida: {not spark.catalog.tableExists(COPIA)}")
    print(f"fato intocada: {spark.table(FATO).count() == linhas}")


if __name__ == "__main__":
    main()
