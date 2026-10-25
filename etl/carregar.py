"""ETL em lote do DW rigido: carrega os CSV de MG de um ano em dw.estacao e dw.medicao."""
import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
CSV_MG = RAIZ / "work" / "csv_mg"
LINHAS_METADADOS = 8
COLUNAS_MEDIDA = [
    "precip_mm", "pressao_mb", "pressao_max_mb", "pressao_min_mb", "radiacao_kjm2",
    "temp_ar_c", "temp_orvalho_c", "temp_max_c", "temp_min_c", "temp_orvalho_max_c",
    "temp_orvalho_min_c", "umid_max_pct", "umid_min_pct", "umid_pct", "vento_dir_gr",
    "vento_rajada_ms", "vento_vel_ms",
]
SQL_COPY = f"COPY dw.medicao (cod, data_hora_utc, {', '.join(COLUNAS_MEDIDA)}) FROM STDIN"
SQL_ESTACAO = """
    INSERT INTO dw.estacao (cod, nome, uf, regiao, latitude, longitude, altitude, data_fundacao)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (cod) DO UPDATE SET
        nome = EXCLUDED.nome, uf = EXCLUDED.uf, regiao = EXCLUDED.regiao,
        latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
        altitude = EXCLUDED.altitude, data_fundacao = EXCLUDED.data_fundacao
"""


def decimal(texto: str) -> float | None:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def valor(texto: str) -> str | None:
    return None if texto in ("", "-9999") else texto.replace(",", ".")


def ler_csv(caminho: Path) -> tuple[tuple, list[tuple]]:
    with caminho.open(encoding="latin-1", newline="") as fh:
        linhas = list(csv.reader(fh, delimiter=";"))
    meta = [l[1] for l in linhas[:LINHAS_METADADOS]]
    regiao, uf, nome, cod, lat, lon, alt, fundacao = meta
    estacao = (cod, nome, uf, regiao, decimal(lat), decimal(lon), decimal(alt),
               datetime.strptime(fundacao, "%Y-%m-%d").date())
    medicoes = []
    for l in linhas[LINHAS_METADADOS + 1:]:
        if not l:
            continue
        quando = datetime.strptime(f"{l[0]} {l[1]}", "%Y-%m-%d %H:%M")
        medicoes.append((cod, quando, *(valor(v) for v in l[2:2 + len(COLUNAS_MEDIDA)])))
    return estacao, medicoes


def carregar_arquivo(dw: psycopg.Connection, ctl: psycopg.Connection, ano: int, caminho: Path) -> int:
    carga_id = ctl.execute(
        "INSERT INTO dw.carga (ano, arquivo) VALUES (%s, %s) RETURNING id", (ano, caminho.name)
    ).fetchone()[0]
    try:
        estacao, medicoes = ler_csv(caminho)
        with dw.transaction(), dw.cursor() as cur:
            cur.execute(SQL_ESTACAO, estacao)
            cur.execute(
                "DELETE FROM dw.medicao WHERE cod = %s AND EXTRACT(year FROM data_hora_utc) = %s",
                (estacao[0], ano),
            )
            with cur.copy(SQL_COPY) as copia:
                for linha in medicoes:
                    copia.write_row(linha)
    except Exception as erro:
        ctl.execute("UPDATE dw.carga SET status = 'erro', erro = %s, fim = now() WHERE id = %s",
                    (f"{type(erro).__name__}: {erro}", carga_id))
        raise
    ctl.execute("UPDATE dw.carga SET status = 'ok', linhas = %s, fim = now() WHERE id = %s",
                (len(medicoes), carga_id))
    return len(medicoes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, required=True)
    ano = parser.parse_args().ano
    conexao = dict(host="127.0.0.1", port=5440, dbname="inmet_dw",
                   user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"])
    inicio = time.perf_counter()
    total = 0
    with psycopg.connect(**conexao) as dw, psycopg.connect(**conexao, autocommit=True) as ctl:
        arquivos = sorted((CSV_MG / str(ano)).glob("*.CSV"))
        for caminho in arquivos:
            total += carregar_arquivo(dw, ctl, ano, caminho)
    segundos = time.perf_counter() - inicio
    print(f"{ano}: {len(arquivos)} arquivos, {total} linhas, {segundos:.1f}s, {total / segundos:.0f} linhas/s")


if __name__ == "__main__":
    main()
