"""Extrai: abre os zips do raw e lê os CSV como texto bruto, sem interpretar nada."""
import csv
import io
import itertools
import json
import re
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_MG = RAIZ / "work" / "csv_mg"
LINHAS_METADADOS = 8
COD_NOME_DO_ARQUIVO = re.compile(
    r"INMET_\w+_MG_(?P<cod>[A-Z]\d+)_(?P<nome>.+)_\d\d-\d\d-\d{4}_A_\d\d-\d\d-\d{4}\.CSV", re.I)


def extrair_csv_mg() -> None:
    for linha in (RAIZ / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        reg = json.loads(linha)
        pasta = CSV_MG / str(reg["ano"])
        pasta.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(RAIZ / reg["arquivo"]) as z:
            membros = [m for m in z.infolist() if "_MG_" in m.filename and not m.is_dir()]
            for m in membros:
                (pasta / Path(m.filename).name).write_bytes(z.read(m))
        print(f"{reg['ano']}: {len(membros)} CSV de MG")


def listar_arquivos(ano: int) -> list[Path]:
    return sorted((CSV_MG / str(ano)).glob("*.CSV"))


def separar(fonte) -> tuple[list[str], list[list[str]]]:
    linhas = list(csv.reader(fonte, delimiter=";"))
    metadados = [l[1] for l in linhas[:LINHAS_METADADOS]]
    dados = [l for l in linhas[LINHAS_METADADOS + 1:] if l]
    return metadados, dados


def ler_bruto(caminho: Path) -> tuple[list[str], list[list[str]]]:
    with caminho.open(encoding="latin-1", newline="") as fh:
        return separar(fh)


def _csv_do_zip(ano: int, uf: str | None = None):
    registros = map(json.loads, (RAIZ / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines())
    registro = next(r for r in registros if r["ano"] == ano)
    with zipfile.ZipFile(RAIZ / registro["arquivo"]) as z:
        for membro in sorted(z.infolist(), key=lambda m: m.filename):
            nome = Path(membro.filename).name
            if membro.is_dir() or not nome.upper().endswith(".CSV") or (uf and f"_{uf}_" not in nome):
                continue
            with z.open(membro) as bruto:
                yield nome, io.TextIOWrapper(bruto, encoding="latin-1", newline="")


def ler_do_zip(ano: int, uf: str | None = None):
    """Devolve (nome do arquivo, (metadados, dados)) de cada CSV do ano, lido direto do zip."""
    for nome, texto in _csv_do_zip(ano, uf):
        yield nome, separar(texto)


def cabecalhos_do_zip(ano: int):
    """Devolve (nome do arquivo, metadados) de cada CSV do ano, lendo só as linhas de metadados."""
    for nome, texto in _csv_do_zip(ano):
        yield nome, [linha[1] for linha in itertools.islice(csv.reader(texto, delimiter=";"), LINHAS_METADADOS)]


if __name__ == "__main__":
    extrair_csv_mg()
