"""Extrai os CSV de MG de cada zip do raw para work/csv_mg/<ano>/, sem tocar no raw."""
import json
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "work" / "csv_mg"


def main() -> None:
    for linha in (RAIZ / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        reg = json.loads(linha)
        pasta = SAIDA / str(reg["ano"])
        pasta.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(RAIZ / reg["arquivo"]) as z:
            membros = [m for m in z.infolist() if "_MG_" in m.filename and not m.is_dir()]
            for m in membros:
                (pasta / Path(m.filename).name).write_bytes(z.read(m))
        print(f"{reg['ano']}: {len(membros)} CSV de MG")


if __name__ == "__main__":
    main()
