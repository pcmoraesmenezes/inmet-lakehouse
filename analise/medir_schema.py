"""Mede o custo de mudar o schema da medicao, numa copia descartavel para nao tocar o baseline."""
import os
import threading
import time

import psycopg

COPIA = "dw.medicao_teste"
ESPERA_LEITOR_S = 1.0


def conexao() -> psycopg.Connection:
    return psycopg.connect(host="127.0.0.1", port=5440, dbname="inmet_dw",
                           user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"], autocommit=True)


def medir(rotulo: str, ctl: psycopg.Connection, sql: str) -> float:
    inicio = time.perf_counter()
    try:
        ctl.execute(sql)
        resultado = f"{time.perf_counter() - inicio:.2f} s"
    except psycopg.Error as erro:
        resultado = f"falhou em {time.perf_counter() - inicio:.2f} s: {str(erro).splitlines()[0]}"
    print(f"{rotulo}: {resultado}")
    return time.perf_counter() - inicio


def tamanho(ctl: psycopg.Connection) -> str:
    return ctl.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{COPIA}'))").fetchone()[0]


def troca_de_tipo_com_leitor(ctl: psycopg.Connection) -> None:
    espera: list[float] = []

    def leitor() -> None:
        time.sleep(ESPERA_LEITOR_S)
        with conexao() as outra:
            inicio = time.perf_counter()
            outra.execute(f"SELECT count(*) FROM {COPIA} WHERE cod = 'A502'").fetchone()
            espera.append(time.perf_counter() - inicio)

    fio = threading.Thread(target=leitor)
    fio.start()
    medir("ALTER COLUMN pressao_mb TYPE double precision (reescreve a tabela)", ctl,
          f"ALTER TABLE {COPIA} ALTER COLUMN pressao_mb TYPE double precision")
    fio.join()
    print(f"  consulta de 1 estacao feita 1 s depois do inicio do ALTER esperou {espera[0]:.2f} s")


def main() -> None:
    with conexao() as ctl:
        ctl.execute(f"DROP TABLE IF EXISTS {COPIA}")
        try:
            medir("copiar a medicao para a tabela de teste", ctl, f"CREATE TABLE {COPIA} (LIKE dw.medicao INCLUDING ALL)")
            medir("  carregar a copia", ctl, f"INSERT INTO {COPIA} SELECT * FROM dw.medicao")
            print(f"tamanho da copia: {tamanho(ctl)}")
            medir("ADD COLUMN sensor_novo real (anula as linhas antigas)", ctl, f"ALTER TABLE {COPIA} ADD COLUMN sensor_novo real")
            medir("ADD COLUMN flag smallint NOT NULL DEFAULT 0", ctl, f"ALTER TABLE {COPIA} ADD COLUMN flag smallint NOT NULL DEFAULT 0")
            troca_de_tipo_com_leitor(ctl)
            medir("ADD CONSTRAINT CHECK (precip_mm >= 0) validando as linhas", ctl,
                  f"ALTER TABLE {COPIA} ADD CONSTRAINT precip_nao_negativa CHECK (precip_mm >= 0)")
            antes = tamanho(ctl)
            medir("UPDATE sensor_novo = 0 em todas as linhas (preencher o historico)", ctl, f"UPDATE {COPIA} SET sensor_novo = 0")
            print(f"tamanho antes e depois do UPDATE: {antes} e {tamanho(ctl)}")
        finally:
            ctl.execute(f"DROP TABLE IF EXISTS {COPIA}")
        existe = ctl.execute("SELECT to_regclass('dw.medicao_teste')").fetchone()[0]
        print(f"copia removida: {existe is None}")


if __name__ == "__main__":
    main()
