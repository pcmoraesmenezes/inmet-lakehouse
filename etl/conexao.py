"""Conexao com o Postgres do DW, configurada por variaveis de ambiente."""
import os

import psycopg


def parametros() -> dict:
    return dict(
        host=os.environ.get("PG_HOST", "127.0.0.1"),
        port=int(os.environ.get("PG_PORT", "5440")),
        dbname=os.environ.get("PG_DB", "inmet_dw"),
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
    )


def abrir(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(**parametros(), autocommit=autocommit)
