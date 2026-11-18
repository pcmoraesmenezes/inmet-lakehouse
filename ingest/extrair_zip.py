"""Extrai do zip do raw os CSV de um ano para o volume, conferindo o sha256 contra o manifesto."""
import hashlib
import json
import zipfile
from pathlib import Path

BLOCO = 1 << 20


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        while bloco := fh.read(BLOCO):
            h.update(bloco)
    return h.hexdigest()


def ler_manifesto(raw: Path) -> dict[int, dict]:
    registros = (json.loads(l) for l in (raw / "manifest.jsonl").read_text(encoding="utf-8").splitlines())
    return {r["ano"]: r for r in registros}


def extrair_ano(raw: Path, ano: int, registro: dict, destino: Path, uf: str | None = None) -> int:
    zip_path = raw / registro["arquivo"]
    obtido = sha256(zip_path)
    if obtido != registro["sha256"]:
        raise ValueError(f"{registro['arquivo']} diverge do manifesto: sha256 {obtido[:16]} contra {registro['sha256'][:16]}")
    pasta = destino / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        membros = [m for m in z.infolist()
                   if not m.is_dir() and m.filename.upper().endswith(".CSV") and (uf is None or f"_{uf}_" in m.filename)]
        for m in membros:
            alvo = pasta / Path(m.filename).name
            if not alvo.exists() or alvo.stat().st_size != m.file_size:
                alvo.write_bytes(z.read(m))
    return len(membros)
