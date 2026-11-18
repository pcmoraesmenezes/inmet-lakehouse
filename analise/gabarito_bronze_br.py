"""Gabarito da bronze nacional: CSV e linhas não vazias por ano e por UF, contados direto dos zips.

A bronze guarda toda linha de texto de cada CSV, então o gabarito é o número de linhas não vazias.
Uso: python3 analise/gabarito_bronze_br.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path
import zipfile

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = Path(__file__).resolve().parent / "gabarito_bronze_br.json"
NOME = re.compile(r"^INMET_[A-Z]+_(?P<uf>[A-Z]{2})_[A-Z]\d+_", re.I)
QUEBRA_DE_LINHA = re.compile(rb"\r\n|\n|\r")


def contar_ano(caminho_zip: Path) -> tuple[dict, list[str]]:
    por_uf: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    fora = []
    with zipfile.ZipFile(caminho_zip) as z:
        for membro in z.infolist():
            nome = Path(membro.filename).name
            if membro.is_dir() or not nome.upper().endswith(".CSV"):
                continue
            casa = NOME.match(nome)
            if not casa:
                fora.append(nome)
                continue
            linhas = sum(1 for l in QUEBRA_DE_LINHA.split(z.read(membro)) if l.strip())
            contagem = por_uf[casa["uf"].upper()]
            contagem[0] += 1
            contagem[1] += linhas
    return dict(por_uf), fora


def main() -> None:
    gabarito, fora_do_padrao = {}, []
    for registro in (json.loads(l) for l in (RAIZ / "raw" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()):
        por_uf, fora = contar_ano(RAIZ / registro["arquivo"])
        fora_do_padrao += fora
        gabarito[registro["ano"]] = {"csv": sum(c for c, _ in por_uf.values()),
                                     "linhas": sum(l for _, l in por_uf.values()),
                                     "por_uf": {uf: {"csv": c, "linhas": l} for uf, (c, l) in sorted(por_uf.items())}}
        print(f"{registro['ano']}: {gabarito[registro['ano']]['csv']} CSV, {gabarito[registro['ano']]['linhas']} linhas, "
              f"MG {por_uf.get('MG', [0, 0])[0]} CSV e {por_uf.get('MG', [0, 0])[1]} linhas", flush=True)
    SAIDA.write_text(json.dumps(gabarito, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"total: {sum(g['csv'] for g in gabarito.values())} CSV, {sum(g['linhas'] for g in gabarito.values())} linhas, "
          f"MG {sum(g['por_uf']['MG']['linhas'] for g in gabarito.values())} linhas")
    print(f"fora do padrao de nome: {len(fora_do_padrao)} {fora_do_padrao[:5]}")


if __name__ == "__main__":
    main()
