"""Transforma: converte o texto bruto nos tipos do DW rigido, assumindo o formato V1."""
from datetime import datetime

COLUNAS_MEDIDA = [
    "precip_mm", "pressao_mb", "pressao_max_mb", "pressao_min_mb", "radiacao_kjm2",
    "temp_ar_c", "temp_orvalho_c", "temp_max_c", "temp_min_c", "temp_orvalho_max_c",
    "temp_orvalho_min_c", "umid_max_pct", "umid_min_pct", "umid_pct", "vento_dir_gr",
    "vento_rajada_ms", "vento_vel_ms",
]


def decimal(texto: str) -> float | None:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def valor(texto: str) -> str | None:
    return None if texto in ("", "-9999") else texto.replace(",", ".")


def transformar(metadados: list[str], dados: list[list[str]]) -> tuple[tuple, list[tuple]]:
    regiao, uf, nome, cod, lat, lon, alt, fundacao = metadados
    estacao = (cod, nome, uf, regiao, decimal(lat), decimal(lon), decimal(alt),
               datetime.strptime(fundacao, "%Y-%m-%d").date())
    medicoes = [
        (cod, datetime.strptime(f"{l[0]} {l[1]}", "%Y-%m-%d %H:%M"),
         *(valor(v) for v in l[2:2 + len(COLUNAS_MEDIDA)]))
        for l in dados
    ]
    return estacao, medicoes
