"""Lê a suíte db/consultas.sql e monta o SQL de cada consulta para um motor e um escopo."""
import re
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "db" / "consultas.sql"
ORIGENS = {
    "postgres": "dw.medicao m JOIN dw.estacao e ON e.cod = m.cod",
    "lakehouse": ("workspace.inmet.gold_fato_medicao_hora m "
                  "JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk"),
}
ESCOPOS = {"MG": "AND e.uf = 'MG'", "BR": ""}
CABECALHO = re.compile(r"^-- (Q\d): (.+?) \| consumidor: (.+)$", re.M)


def ler_suite(arquivo: Path = ARQUIVO) -> dict[str, dict]:
    suite = {}
    for trecho in re.split(r"(?m)^(?=-- Q\d:)", arquivo.read_text(encoding="utf-8")):
        cabecalho = CABECALHO.match(trecho)
        if cabecalho:
            sql = trecho[cabecalho.end():].strip().rstrip(";")
            suite[cabecalho[1]] = {"pergunta": cabecalho[2], "consumidor": cabecalho[3], "sql": sql}
    return suite


def montar(sql: str, motor: str, escopo: str, ano: int = 2024, estacao: str = "A502") -> str:
    return sql.format(origem=ORIGENS[motor], escopo=ESCOPOS[escopo],
                      ano=ano, ano_seguinte=ano + 1, estacao=estacao)
