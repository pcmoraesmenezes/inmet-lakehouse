"""EDA da estrutura dos CSV de MG: esquema, formatos, ausentes, chave e cobertura, sem corrigir nada."""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_MG = RAIZ / "work" / "csv_mg"
SAIDA = RAIZ / "work" / "eda_schema.json"
NOME = re.compile(r"INMET_\w+_MG_(?P<cod>[A-Z]\d+)_.+_(?P<ini>\d\d-\d\d-\d{4})_A_(?P<fim>\d\d-\d\d-\d{4})\.CSV", re.I)
DATA_ISO = re.compile(r"\d{4}-\d\d-\d\d")
DATA_BARRA = re.compile(r"\d{4}/\d\d/\d\d")
HORA_DOIS_PONTOS = re.compile(r"\d\d:\d\d")
HORA_UTC = re.compile(r"\d{4} UTC")


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").upper()


def numero(texto: str) -> float | None:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def dias(ini: str, fim: str) -> int:
    d, m, a = (int(x) for x in ini.split("-"))
    d2, m2, a2 = (int(x) for x in fim.split("-"))
    return (date(a2, m2, d2) - date(a, m, d)).days + 1


def classe_data(v: str) -> str:
    return "iso" if DATA_ISO.fullmatch(v) else "barra" if DATA_BARRA.fullmatch(v) else "outra"


def classe_hora(v: str) -> str:
    return "hh:mm" if HORA_DOIS_PONTOS.fullmatch(v) else "hhmm UTC" if HORA_UTC.fullmatch(v) else "outra"


def chave_normalizada(data: str, hora: str) -> str:
    return data.replace("/", "-") + " " + hora.replace(":", "").replace(" UTC", "")


def ler_arquivo(caminho: Path, ano: int) -> dict:
    bruto = caminho.read_bytes()
    try:
        texto, codificacao = bruto.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        texto, codificacao = bruto.decode("latin-1"), "latin-1"
    linhas = texto.splitlines()
    idx = next(i for i, l in enumerate(linhas) if "PRECIPITA" in sem_acento(l))
    meta = [(l.split(";", 1) + [""])[:2] for l in linhas[:idx]]
    cabecalho = linhas[idx].split(";")
    dados = [l for l in linhas[idx + 1:] if l.strip()]
    m = NOME.fullmatch(caminho.name)
    campos_meta = {sem_acento(k).strip(): v.strip() for k, v in meta}
    registro = {
        "ano": ano, "arquivo": caminho.name, "cod": m["cod"], "codificacao": codificacao,
        "crlf": b"\r\n" in bruto, "tamanho_meta": idx, "rotulos_meta": [k for k, _ in meta],
        "colunas": cabecalho, "n_colunas": len(cabecalho), "linhas": len(dados),
        "esperadas": dias(m["ini"], m["fim"]) * 24,
        "cod_cabecalho": campos_meta.get("CODIGO (WMO):"),
        "lat": numero(campos_meta.get("LATITUDE:", "")), "lon": numero(campos_meta.get("LONGITUDE:", "")),
        "alt": numero(campos_meta.get("ALTITUDE:", "")),
    }
    datas, horas, chaves = Counter(), Counter(), Counter()
    ausentes = Counter()
    nao_numericos: Counter = Counter()
    ponto_decimal = 0
    desalinhadas = 0
    por_coluna: dict[int, Counter] = defaultdict(Counter)
    for linha in dados:
        campos = linha.split(";")
        if len(campos) != len(cabecalho):
            desalinhadas += 1
            continue
        datas[classe_data(campos[0])] += 1
        horas[classe_hora(campos[1])] += 1
        chaves[chave_normalizada(campos[0], campos[1])] += 1
        for i, v in enumerate(campos[2:-1], start=2):
            if v == "":
                tipo = "vazio"
            elif v == "-9999":
                tipo = "-9999"
            elif numero(v) is None:
                tipo = "texto"
                nao_numericos[v] += 1
            else:
                tipo = "numero"
                if "." in v:
                    ponto_decimal += 1
            por_coluna[i][tipo] += 1
            ausentes[tipo] += 1
    registro.update({
        "datas": dict(datas), "horas": dict(horas), "duplicadas": sum(c - 1 for c in chaves.values() if c > 1),
        "desalinhadas": desalinhadas, "celulas": dict(ausentes), "nao_numericos": dict(nao_numericos),
        "ponto_decimal": ponto_decimal,
        "por_coluna": {str(i): dict(c) for i, c in por_coluna.items()},
    })
    return registro


def resumo(registros: list[dict]) -> None:
    anos = sorted({r["ano"] for r in registros})
    print(f"arquivos: {len(registros)}, anos: {anos[0]}-{anos[-1]}\n")

    print("1. TABELA (por ano: codificacao, CRLF, linhas de metadados, colunas)")
    for a in anos:
        rs = [r for r in registros if r["ano"] == a]
        print(f"  {a}: {dict(Counter(r['codificacao'] for r in rs))} crlf={sum(r['crlf'] for r in rs)}/{len(rs)} "
              f"meta={sorted({r['tamanho_meta'] for r in rs})} colunas={sorted({r['n_colunas'] for r in rs})}")

    print("\n2. ESQUEMA (assinatura do cabecalho: bruta e sem acento/caixa)")
    bruta: dict[tuple, set] = defaultdict(set)
    norm: dict[tuple, set] = defaultdict(set)
    for r in registros:
        bruta[tuple(r["colunas"])].add(r["ano"])
        norm[tuple(sem_acento(c) for c in r["colunas"])].add(r["ano"])
    print(f"  versoes brutas: {len(bruta)}; versoes depois de tirar acento e caixa: {len(norm)}")
    for i, (sig, an) in enumerate(sorted(bruta.items(), key=lambda kv: min(kv[1])), 1):
        print(f"  bruta {i}: anos {sorted(an)}")
    base = sorted(norm.items(), key=lambda kv: -len(kv[1]))[0][0]
    for sig, an in norm.items():
        if sig != base:
            dif = [(a, b) for a, b in zip(base, sig) if a != b]
            print(f"  normalizada diferente em {sorted(an)}: {dif[:4]}")
    print("  rotulos de metadados por ano:", {a: sorted({tuple(r['rotulos_meta'][:1] + r['rotulos_meta'][-1:]) for r in registros if r['ano'] == a}) for a in anos[:1] + anos[-1:]})

    print("\n3. FORMATO por ano (data / hora / linhas com ponto decimal)")
    for a in anos:
        rs = [r for r in registros if r["ano"] == a]
        d = sum((Counter(r["datas"]) for r in rs), Counter())
        h = sum((Counter(r["horas"]) for r in rs), Counter())
        print(f"  {a}: data {dict(d)} hora {dict(h)} ponto_decimal={sum(r['ponto_decimal'] for r in rs)}")

    print("\n4. AUSENTES por ano (% das celulas de medida: vazio / -9999 / texto)")
    for a in anos:
        c = sum((Counter(r["celulas"]) for r in registros if r["ano"] == a), Counter())
        t = sum(c.values())
        print(f"  {a}: vazio {100*c['vazio']/t:5.1f}%  -9999 {100*c['-9999']/t:5.1f}%  texto {100*c['texto']/t:4.2f}%  numero {100*c['numero']/t:5.1f}%")
    tokens = sum((Counter(r["nao_numericos"]) for r in registros), Counter())
    print("  tokens nao numericos mais comuns:", tokens.most_common(5))

    print("\n5. CHAVE (codigo + data/hora)")
    print(f"  linhas duplicadas pela chave normalizada: {sum(r['duplicadas'] for r in registros)}; linhas desalinhadas: {sum(r['desalinhadas'] for r in registros)}")
    ruim = [(r["ano"], r["cod"], r["cod_cabecalho"]) for r in registros if r["cod"] != r["cod_cabecalho"]]
    print(f"  codigo do cabecalho diferente do nome do arquivo: {len(ruim)} {ruim[:5]}")

    print("\n6. COBERTURA (linhas contra horas esperadas pelo periodo do nome)")
    for a in anos:
        rs = [r for r in registros if r["ano"] == a]
        falta = sum(max(r["esperadas"] - r["linhas"], 0) for r in rs)
        sobra = sum(max(r["linhas"] - r["esperadas"], 0) for r in rs)
        iguais = sum(r["linhas"] == r["esperadas"] for r in rs)
        print(f"  {a}: iguais {iguais}/{len(rs)}, linhas faltando {falta}, linhas a mais {sobra}")

    print("\n7. METADADOS DA ESTACAO ao longo dos anos")
    por_cod: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_cod[r["cod"]].append(r)
    for campo in ("alt", "lat", "lon"):
        mudou = []
        for cod, rs in por_cod.items():
            vs = [r[campo] for r in rs if r[campo] is not None]
            if len(set(vs)) > 1:
                mudou.append((cod, max(vs) - min(vs)))
        print(f"  {campo}: {len(mudou)} de {len(por_cod)} estacoes com mais de um valor; maior variacao {max((d for _, d in mudou), default=0):.5f}")


def main() -> None:
    registros = []
    for pasta in sorted(CSV_MG.iterdir()):
        for arq in sorted(pasta.glob("*")):
            registros.append(ler_arquivo(arq, int(pasta.name)))
    SAIDA.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
    resumo(registros)


if __name__ == "__main__":
    main()
