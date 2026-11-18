"""Roda o ETL de um ou mais anos: transforma e carrega cada arquivo, registrando na carga."""
import argparse
import time

import psycopg

from etl.carregar import abrir_carga, carregar, falhar_carga, fechar_carga
from etl.conexao import abrir
from etl.extrair import ler_bruto, ler_do_zip, listar_arquivos
from etl.transformar import transformar


def do_disco(ano: int):
    for caminho in listar_arquivos(ano):
        yield caminho.name, ler_bruto(caminho)


def processar(dw: psycopg.Connection, ctl: psycopg.Connection, ano: int, nome: str, bruto: tuple) -> int:
    carga_id = abrir_carga(ctl, ano, nome)
    try:
        estacao, medicoes = transformar(*bruto)
        carregar(dw, ano, estacao, medicoes)
    except Exception as erro:
        falhar_carga(ctl, carga_id, f"{type(erro).__name__}: {erro}")
        raise
    fechar_carga(ctl, carga_id, len(medicoes))
    return len(medicoes)


def carregar_ano(dw: psycopg.Connection, ctl: psycopg.Connection, ano: int, arquivos=None) -> tuple[int, int]:
    arquivos = do_disco(ano) if arquivos is None else arquivos
    quantos = total = 0
    for nome, bruto in arquivos:
        total += processar(dw, ctl, ano, nome, bruto)
        quantos += 1
    return quantos, total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, nargs="+", required=True)
    parser.add_argument("--zip", action="store_true", help="le direto dos zips do raw, em vez de work/csv_mg")
    parser.add_argument("--uf", help="com --zip, so os arquivos desta UF")
    args = parser.parse_args()
    with abrir() as dw, abrir(autocommit=True) as ctl:
        for ano in args.ano:
            inicio = time.perf_counter()
            arquivos, total = carregar_ano(dw, ctl, ano, ler_do_zip(ano, args.uf) if args.zip else None)
            segundos = time.perf_counter() - inicio
            tamanho_mb = ctl.execute("SELECT pg_database_size(current_database()) / 1048576").fetchone()[0]
            print(f"{ano}: {arquivos} arquivos, {total} linhas, {segundos:.1f}s, {total / segundos:.0f} linhas/s, "
                  f"banco com {tamanho_mb} MB", flush=True)


if __name__ == "__main__":
    main()
