"""Gabarito da prata e da ouro nacionais, contado direto dos zips: linhas por ano e linhas da dimensão.

Prata: linhas com ao menos uma medida válida, de qualquer estação. Ouro: as dessas linhas cuja estação passa em geo.na_uf.
Uso: python3 -m analise.gabarito_ouro_br
"""
import json
from pathlib import Path

import pandas as pd

from analise import geo
from etl import dimensao
from etl.extrair import ler_do_zip
from etl.transformar import COLUNAS_MEDIDA, decimal

SAIDA = Path(__file__).resolve().parent / "gabarito_ouro_br.json"
LIMITE_RADIACAO_KJM2 = 5000
RADIACAO = COLUNAS_MEDIDA.index("radiacao_kjm2")
ANOS = range(2016, 2026)


def tem_medida(linha: list[str]) -> bool:
    for i, texto in enumerate(linha[2:2 + len(COLUNAS_MEDIDA)]):
        if texto in ("", "-9999"):
            continue
        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            continue
        if i == RADIACAO and valor > LIMITE_RADIACAO_KJM2:
            continue
        return True
    return False


def main() -> None:
    contornos = geo.carregar_contornos()
    estacoes, por_ano = [], {}
    for ano in ANOS:
        prata = fato = fato_mg = 0
        for _, (metadados, dados) in ler_do_zip(ano):
            regiao, uf, nome, cod, lat, lon, alt, _ = metadados
            lat, lon = decimal(lat), decimal(lon)
            em_uf = lat is not None and lon is not None and uf in contornos and geo.na_uf(lon, lat, contornos[uf])
            linhas = sum(1 for l in dados if tem_medida(l))
            prata += linhas
            if em_uf:
                fato += linhas
                fato_mg += linhas if uf == "MG" else 0
                estacoes.append(dict(cod=cod, ano=ano, nome=nome, uf=uf, regiao=regiao, lat=lat, lon=lon,
                                     alt=decimal(alt), data_fundacao=None))
        por_ano[ano] = {"prata": prata, "fato": fato, "fato_mg": fato_mg}
        print(f"{ano}: prata {prata}, fato {fato}, fato de MG {fato_mg}", flush=True)
    dim = dimensao.versionar(pd.DataFrame(estacoes))
    resumo = {"linhas": len(dim), "estacoes": int(dim.cod.nunique()), "linhas_mg": int((dim.uf == "MG").sum()),
              "estacoes_com_mais_de_uma_versao": int((dim.groupby("cod").size() > 1).sum())}
    SAIDA.write_text(json.dumps({"por_ano": por_ano, "dimensao": resumo}, indent=1) + "\n", encoding="utf-8")
    print(f"total: prata {sum(v['prata'] for v in por_ano.values())}, fato {sum(v['fato'] for v in por_ano.values())}, "
          f"fato de MG {sum(v['fato_mg'] for v in por_ano.values())}")
    print(f"dimensão: {resumo}")


if __name__ == "__main__":
    main()
