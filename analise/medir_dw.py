"""Mede o DW rigido: tamanho, reprocessamento da menor unidade e consultas por dia."""
import re
import time

import psycopg

from etl.conexao import abrir
from etl.extrair import CSV_MG
from etl.rodar import processar

ANO, ESTACAO, DIA = 2025, "A502", "2025-03-15"
REPETICOES = 3
CONSULTA_DIA = ("SELECT count(*) FROM dw.medicao WHERE data_hora_utc >= %s "
                "AND data_hora_utc < %s::date + 1")


def tempo_da_consulta(cur: psycopg.Cursor, sql: str, params: tuple) -> float:
    cur.execute("EXPLAIN (ANALYZE) " + sql, params)
    texto = "\n".join(linha[0] for linha in cur.fetchall())
    return float(re.search(r"Execution Time: ([\d.]+) ms", texto).group(1))


def main() -> None:
    with abrir() as dw, abrir(autocommit=True) as ctl:
        cur = dw.cursor()
        cur.execute("SELECT count(*), pg_size_pretty(pg_relation_size('dw.medicao')), "
                    "pg_size_pretty(pg_indexes_size('dw.medicao')), pg_size_pretty(pg_database_size(current_database())) "
                    "FROM dw.medicao")
        linhas, tabela, indice, banco = cur.fetchone()
        print(f"medicao: {linhas} linhas, tabela {tabela}, indices {indice}, banco {banco}")

        arquivo = next((CSV_MG / str(ANO)).glob(f"*_{ESTACAO}_*.CSV"))
        tempos = []
        for _ in range(REPETICOES):
            inicio = time.perf_counter()
            regravadas = processar(dw, ctl, ANO, arquivo)
            tempos.append(time.perf_counter() - inicio)
        print(f"reprocessar {ESTACAO} de {ANO}, a menor unidade do ETL: {regravadas} linhas, "
              f"{', '.join(f'{t:.2f}s' for t in tempos)}")

        inicio = time.perf_counter()
        cur.execute("DELETE FROM dw.medicao WHERE cod = %s AND data_hora_utc >= %s AND data_hora_utc < %s::date + 1",
                    (ESTACAO, DIA, DIA))
        apagadas = cur.rowcount
        dw.rollback()
        print(f"DELETE de 1 dia da {ESTACAO} ({apagadas} linhas, descartado): {(time.perf_counter() - inicio) * 1000:.1f} ms")

        print(f"consulta de 1 dia, todas as estacoes: {tempo_da_consulta(cur, CONSULTA_DIA, (DIA, DIA)):.1f} ms")
        por_estacao = CONSULTA_DIA + " AND cod = %s"
        print(f"consulta de 1 dia, 1 estacao: {tempo_da_consulta(cur, por_estacao, (DIA, DIA, ESTACAO)):.1f} ms")


if __name__ == "__main__":
    main()
