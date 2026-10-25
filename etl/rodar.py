"""Roda o ETL de um ano: extrai, transforma e carrega cada arquivo, registrando na carga."""
import argparse
import time
from pathlib import Path

import psycopg

from etl.carregar import abrir_carga, carregar, falhar_carga, fechar_carga
from etl.conexao import abrir
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


def carregar_ano(dw: psycopg.Connection, ctl: psycopg.Connection, ano: int) -> tuple[int, int]:
    arquivos = listar_arquivos(ano)
    total = sum(processar(dw, ctl, ano, caminho) for caminho in arquivos)
    return len(arquivos), total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, required=True)
    ano = parser.parse_args().ano
    inicio = time.perf_counter()
    with abrir() as dw, abrir(autocommit=True) as ctl:
        arquivos, total = carregar_ano(dw, ctl, ano)
    segundos = time.perf_counter() - inicio
    print(f"{ano}: {arquivos} arquivos, {total} linhas, {segundos:.1f}s, {total / segundos:.0f} linhas/s")


if __name__ == "__main__":
    main()
