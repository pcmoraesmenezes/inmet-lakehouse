"""Confere a carga nacional no Postgres contra o gabarito dos zips: linhas por ano, linhas de MG e partição residual.

O banco conferido é o de PG_DB. Cada CSV tem 9 linhas que não são medição (8 de metadados e o cabeçalho).
Uso: PG_DB=inmet_br_rigido python -m analise.conferir_carga_br
"""
import json
import sys
from pathlib import Path

from etl.conexao import abrir

GABARITO = Path(__file__).resolve().parent / "gabarito_bronze_br.json"
LINHAS_QUE_NAO_SAO_MEDICAO = 9


def esperado() -> dict[int, tuple[int, int]]:
    gabarito = json.loads(GABARITO.read_text(encoding="utf-8"))
    return {int(ano): (g["linhas"] - LINHAS_QUE_NAO_SAO_MEDICAO * g["csv"],
                       g["por_uf"]["MG"]["linhas"] - LINHAS_QUE_NAO_SAO_MEDICAO * g["por_uf"]["MG"]["csv"])
            for ano, g in gabarito.items()}


def main() -> None:
    anos = {int(a) for a in sys.argv[1:]}
    falhou = False
    total = 0
    with abrir() as dw, dw.cursor() as cur:
        for ano, (linhas, linhas_mg) in sorted(esperado().items()):
            if anos and ano not in anos:
                continue
            cur.execute(
                "SELECT count(*), count(*) FILTER (WHERE e.uf = 'MG') FROM dw.medicao m JOIN dw.estacao e USING (cod) "
                "WHERE m.data_hora_utc >= make_date(%s, 1, 1) AND m.data_hora_utc < make_date(%s + 1, 1, 1)",
                (ano, ano))
            no_banco, mg_no_banco = cur.fetchone()
            ok = (no_banco, mg_no_banco) == (linhas, linhas_mg)
            falhou |= not ok
            total += no_banco
            print(f"{ano}: {'OK' if ok else 'DIVERGE'} linhas {no_banco}/{linhas}, MG {mg_no_banco}/{linhas_mg}")
        cur.execute("SELECT to_regclass('dw.medicao_outros') IS NOT NULL")
        residual = 0
        if cur.fetchone()[0]:
            cur.execute("SELECT count(*) FROM dw.medicao_outros")
            residual = cur.fetchone()[0]
    falhou |= residual != 0
    print(f"total {total}, partição residual com {residual} linhas")
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
