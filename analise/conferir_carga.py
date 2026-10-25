"""Confere a carga de um ano contra os CSV: linhas, estacoes e, por coluna, contagem e soma."""
import argparse
import csv
import os
import sys

import psycopg

from etl.extrair import ler_bruto, listar_arquivos
from etl.transformar import COLUNAS_MEDIDA

TOLERANCIA_SOMA = 1e-6


def do_csv(ano: int) -> tuple[int, int, list[int], list[float]]:
    arquivos = listar_arquivos(ano)
    linhas, contagem, soma = 0, [0] * len(COLUNAS_MEDIDA), [0.0] * len(COLUNAS_MEDIDA)
    for caminho in arquivos:
        _, dados = ler_bruto(caminho)
        linhas += len(dados)
        for l in dados:
            for i, v in enumerate(l[2:2 + len(COLUNAS_MEDIDA)]):
                if v not in ("", "-9999"):
                    contagem[i] += 1
                    soma[i] += float(v.replace(",", "."))
    return linhas, len(arquivos), contagem, soma


def do_banco(cur: psycopg.Cursor, ano: int) -> tuple[int, int, list[int], list[float]]:
    agregados = ", ".join(f"count({c}), coalesce(sum({c}::double precision), 0)" for c in COLUNAS_MEDIDA)
    cur.execute(
        f"SELECT count(*), count(DISTINCT cod), {agregados} FROM dw.medicao "
        "WHERE EXTRACT(year FROM data_hora_utc) = %s", (ano,))
    linha = cur.fetchone()
    return linha[0], linha[1], list(linha[2::2]), list(linha[3::2])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("anos", type=int, nargs="+")
    anos = parser.parse_args().anos
    conexao = dict(host="127.0.0.1", port=5440, dbname="inmet_dw",
                   user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"])
    falhou = False
    with psycopg.connect(**conexao) as dw, dw.cursor() as cur:
        for ano in anos:
            csv_linhas, csv_est, csv_cont, csv_soma = do_csv(ano)
            db_linhas, db_est, db_cont, db_soma = do_banco(cur, ano)
            dif = max((abs(a - b) / max(abs(a), 1e-9) for a, b in zip(csv_soma, db_soma)), default=0)
            ok = (csv_linhas, csv_est, csv_cont) == (db_linhas, db_est, db_cont) and dif < TOLERANCIA_SOMA
            falhou |= not ok
            print(f"{ano}: {'OK' if ok else 'DIVERGE'} linhas {db_linhas}/{csv_linhas}, estacoes {db_est}/{csv_est}, "
                  f"contagens por coluna {'iguais' if csv_cont == db_cont else 'DIFERENTES'}, "
                  f"maior diferenca relativa das somas {dif:.1e}")
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
