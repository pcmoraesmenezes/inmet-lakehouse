"""Extrai: abre os zips do raw e lê os CSV de MG como texto bruto, sem interpretar nada."""
import csv
import json
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_MG = RAIZ / "work" / "csv_mg"
LINHAS_METADADOS = 8


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


def ler_bruto(caminho: Path) -> tuple[list[str], list[list[str]]]:
    with caminho.open(encoding="latin-1", newline="") as fh:
        linhas = list(csv.reader(fh, delimiter=";"))
    metadados = [l[1] for l in linhas[:LINHAS_METADADOS]]
    dados = [l for l in linhas[LINHAS_METADADOS + 1:] if l]
    return metadados, dados


if __name__ == "__main__":
    extrair_csv_mg()
