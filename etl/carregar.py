"""Carrega: grava estacao e medicao no Postgres sobrescrevendo o ano, e registra cada carga."""
import psycopg

from etl.transformar import COLUNAS_MEDIDA

SQL_COPY = f"COPY dw.medicao (cod, data_hora_utc, {', '.join(COLUNAS_MEDIDA)}) FROM STDIN"
SQL_ESTACAO = """
    INSERT INTO dw.estacao (cod, nome, uf, regiao, latitude, longitude, altitude, data_fundacao)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (cod) DO UPDATE SET
        nome = EXCLUDED.nome, uf = EXCLUDED.uf, regiao = EXCLUDED.regiao,
        latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
        altitude = EXCLUDED.altitude, data_fundacao = EXCLUDED.data_fundacao
"""


def carregar(dw: psycopg.Connection, ano: int, estacao: tuple, medicoes: list[tuple]) -> None:
    with dw.transaction(), dw.cursor() as cur:
        cur.execute(SQL_ESTACAO, estacao)
        cur.execute(
            "DELETE FROM dw.medicao WHERE cod = %s AND EXTRACT(year FROM data_hora_utc) = %s",
            (estacao[0], ano),
        )
        with cur.copy(SQL_COPY) as copia:
            for linha in medicoes:
                copia.write_row(linha)


def abrir_carga(ctl: psycopg.Connection, ano: int, arquivo: str) -> int:
    return ctl.execute(
        "INSERT INTO dw.carga (ano, arquivo) VALUES (%s, %s) RETURNING id", (ano, arquivo)
    ).fetchone()[0]


def fechar_carga(ctl: psycopg.Connection, carga_id: int, linhas: int) -> None:
    ctl.execute("UPDATE dw.carga SET status = 'ok', linhas = %s, fim = now() WHERE id = %s",
                (linhas, carga_id))


def falhar_carga(ctl: psycopg.Connection, carga_id: int, erro: str) -> None:
    ctl.execute("UPDATE dw.carga SET status = 'erro', erro = %s, fim = now() WHERE id = %s",
                (erro, carga_id))
