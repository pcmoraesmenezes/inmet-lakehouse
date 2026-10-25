"""Compara, por codigo de estacao, quais estacoes de MG existem em cada ano."""
import re
from pathlib import Path

CSV_MG = Path(__file__).resolve().parent.parent / "work" / "csv_mg"
NOME = re.compile(r"INMET_\w+_MG_(?P<cod>[A-Z]\d+)_(?P<nome>.+)_(?P<ini>\d\d-\d\d-\d{4})_A_(?P<fim>\d\d-\d\d-\d{4})\.CSV", re.I)


def ler() -> tuple[dict[str, dict[int, tuple[str, str]]], dict[str, set[str]]]:
    por_cod: dict[str, dict[int, tuple[str, str]]] = {}
    nomes: dict[str, set[str]] = {}
    for pasta in sorted(CSV_MG.iterdir()):
        ano = int(pasta.name)
        for arq in pasta.glob("*"):
            m = NOME.fullmatch(arq.name)
            if not m:
                print("nome fora do padrao:", ano, arq.name)
                continue
            por_cod.setdefault(m["cod"], {})[ano] = (m["ini"], m["fim"])
            nomes.setdefault(m["cod"], set()).add(m["nome"])
    return por_cod, nomes


def main() -> None:
    por_cod, nomes = ler()
    anos = sorted({a for v in por_cod.values() for a in v})
    print("estacoes distintas:", len(por_cod))
    print("por ano:", {a: sum(a in v for v in por_cod.values()) for a in anos})
    print("\nlinha do tempo (x = tem arquivo)  " + " ".join(str(a)[2:] for a in anos))
    irregulares = []
    for cod in sorted(por_cod, key=lambda c: (min(por_cod[c]), c)):
        presenca = por_cod[cod]
        marca = " ".join(" x" if a in presenca else " ." for a in anos)
        lacuna = any(a not in presenca for a in range(min(presenca), max(presenca) + 1))
        if len(presenca) < len(anos):
            print(f"{cod:5} {sorted(nomes[cod])[0][:22]:22} {marca}{'  VOLTA' if lacuna else ''}")
        for a, (ini, fim) in presenca.items():
            if ini != f"01-01-{a}" or fim != f"31-12-{a}":
                irregulares.append((cod, a, ini, fim))
    print("\ncobertura diferente do ano cheio:", len(irregulares), "arquivos")
    for r in irregulares[:12]:
        print("  ", r)
    print("\ncodigo com mais de um nome:", {c: sorted(n) for c, n in nomes.items() if len(n) > 1})


if __name__ == "__main__":
    main()
