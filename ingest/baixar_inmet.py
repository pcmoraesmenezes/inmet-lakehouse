"""Baixa os zips anuais do INMET para a bronze e registra cada download no manifesto."""
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRONZE = RAIZ / "bronze"
MANIFESTO = BRONZE / "manifest.jsonl"
URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
BLOCO = 1 << 20


def baixar(ano: int) -> dict:
    agora = datetime.now(timezone.utc)
    destino = BRONZE / "zips" / str(ano) / f"{agora:%Y%m%dT%H%M%SZ}.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pedido = urllib.request.Request(URL.format(ano=ano), headers={"User-Agent": "Mozilla/5.0"})
    sha = hashlib.sha256()
    with urllib.request.urlopen(pedido, timeout=120) as resp, destino.open("wb") as saida:
        esperado = int(resp.headers["Content-Length"])
        ultima_mod = resp.headers.get("Last-Modified")
        while bloco := resp.read(BLOCO):
            sha.update(bloco)
            saida.write(bloco)
    tamanho = destino.stat().st_size
    if tamanho != esperado:
        destino.unlink()
        raise RuntimeError(f"{ano}: recebidos {tamanho} de {esperado} bytes")
    return {
        "ano": ano,
        "url": URL.format(ano=ano),
        "arquivo": str(destino.relative_to(RAIZ)),
        "bytes": tamanho,
        "sha256": sha.hexdigest(),
        "last_modified": ultima_mod,
        "baixado_em": agora.isoformat(timespec="seconds"),
    }


def main(anos: list[int]) -> None:
    BRONZE.mkdir(exist_ok=True)
    for ano in anos:
        registro = baixar(ano)
        with MANIFESTO.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        print(f"{ano}: {registro['bytes']} bytes, sha256 {registro['sha256'][:16]}, Last-Modified {registro['last_modified']}")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]])
