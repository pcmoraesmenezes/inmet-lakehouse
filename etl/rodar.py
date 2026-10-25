"""Roda o ETL de um ano: extrai, transforma e carrega cada arquivo, registrando na carga."""
import argparse
import os
import time
from pathlib import Path

import psycopg

from etl.carregar import abrir_carga, carregar, falhar_carga, fechar_carga
from etl.extrair import ler_bruto, listar_arquivos
from etl.transformar import transformar


def processar(dw: psycopg.Connection, ctl: psycopg.Connection, ano: int, caminho: Path) -> int:
    carga_id = abrir_carga(ctl, ano, caminho.name)
    try:
        metadados, dados = ler_bruto(caminho)
        estacao, medicoes = transformar(metadados, dados)
        carregar(dw, ano, estacao, medicoes)
    except Exception as erro:
        falhar_carga(ctl, carga_id, f"{type(erro).__name__}: {erro}")
        raise
    fechar_carga(ctl, carga_id, len(medicoes))
    return len(medicoes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, required=True)
    ano = parser.parse_args().ano
    conexao = dict(host="127.0.0.1", port=5440, dbname="inmet_dw",
                   user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"])
    inicio = time.perf_counter()
    total = 0
    arquivos = listar_arquivos(ano)
    with psycopg.connect(**conexao) as dw, psycopg.connect(**conexao, autocommit=True) as ctl:
        for caminho in arquivos:
            total += processar(dw, ctl, ano, caminho)
    segundos = time.perf_counter() - inicio
    print(f"{ano}: {len(arquivos)} arquivos, {total} linhas, {segundos:.1f}s, {total / segundos:.0f} linhas/s")


if __name__ == "__main__":
    main()
