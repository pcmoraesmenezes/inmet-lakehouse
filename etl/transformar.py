"""Transforma: converte o texto bruto nos tipos do DW rigido, nos formatos V1, V2 e V3."""
from datetime import datetime

COLUNAS_MEDIDA = [
    "precip_mm", "pressao_mb", "pressao_max_mb", "pressao_min_mb", "radiacao_kjm2",
    "temp_ar_c", "temp_orvalho_c", "temp_max_c", "temp_min_c", "temp_orvalho_max_c",
    "temp_orvalho_min_c", "umid_max_pct", "umid_min_pct", "umid_pct", "vento_dir_gr",
    "vento_rajada_ms", "vento_vel_ms",
]
FORMATOS_FUNDACAO = ("%Y-%m-%d", "%d/%m/%y")
HORA_DIA_UTC = (10, 20)
HORA_NOITE_UTC = (23, 8)
DESLOCAMENTO_LOCAL_H = -3
FORMATOS_DATA_HORA = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H%M UTC")


def periodo_do_dia(hora_utc: int) -> str:
    if HORA_DIA_UTC[0] <= hora_utc <= HORA_DIA_UTC[1]:
        return "dia"
    if hora_utc >= HORA_NOITE_UTC[0] or hora_utc <= HORA_NOITE_UTC[1]:
        return "noite"
    return "transicao"


def decimal(texto: str) -> float | None:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def valor(texto: str) -> str | None:
    return None if texto in ("", "-9999") else texto.replace(",", ".")


def escolher_formato(texto: str, formatos: tuple[str, ...]) -> str:
    for formato in formatos:
        try:
            datetime.strptime(texto, formato)
            return formato
        except ValueError:
            continue
    raise ValueError(f"formato de data desconhecido: {texto!r}")


def transformar(metadados: list[str], dados: list[list[str]]) -> tuple[tuple, list[tuple]]:
    regiao, uf, nome, cod, lat, lon, alt, fundacao = metadados
    formato_fundacao = escolher_formato(fundacao, FORMATOS_FUNDACAO)
    estacao = (cod, nome, uf, regiao, decimal(lat), decimal(lon), decimal(alt),
               datetime.strptime(fundacao, formato_fundacao).date())
    formato_hora = escolher_formato(f"{dados[0][0]} {dados[0][1]}", FORMATOS_DATA_HORA)
    medicoes = [
        (cod, datetime.strptime(f"{l[0]} {l[1]}", formato_hora),
         *(valor(v) for v in l[2:2 + len(COLUNAS_MEDIDA)]))
        for l in dados
    ]
    return estacao, medicoes
