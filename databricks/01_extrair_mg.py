import hashlib
import json
import zipfile
from pathlib import Path

VOLUME = "/Volumes/workspace/inmet/raw/zips"
BLOCO = 1 << 20


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        while bloco := fh.read(BLOCO):
            h.update(bloco)
    return h.hexdigest()


def ler_manifesto(volume: Path) -> dict[int, dict]:
    registros = (json.loads(l) for l in (Path(volume).parent / "manifest.jsonl").read_text(encoding="utf-8").splitlines())
    return {r["ano"]: r for r in registros}


def extrair_ano(volume: Path, ano: int, reg: dict) -> int:
    zip_path = volume.parent / reg["arquivo"]
    obtido = sha256(zip_path)
    if obtido != reg["sha256"]:
        raise ValueError(f"{reg['arquivo']} diverge do manifesto: sha256 {obtido[:16]} contra {reg['sha256'][:16]}")
    destino = volume / "csv_mg" / str(ano)
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        membros = [m for m in z.infolist() if "_MG_" in m.filename and not m.is_dir()]
        for m in membros:
            alvo = destino / Path(m.filename).name
            if not alvo.exists() or alvo.stat().st_size != m.file_size:
                alvo.write_bytes(z.read(m))
    return len(membros)


def extrair_tudo(volume: str) -> list[tuple[int, int]]:
    raiz = Path(volume)
    manifesto = ler_manifesto(raiz)
    return [(ano, extrair_ano(raiz, ano, reg)) for ano, reg in sorted(manifesto.items())]


if __name__ == "__main__":
    for ano, arquivos in extrair_tudo(VOLUME):
        print(f"{ano}: {arquivos} CSV de MG")
