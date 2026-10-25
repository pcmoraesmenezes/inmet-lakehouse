"""Um tick do agendador: entrega ao DW o proximo ano de MG, simulando a publicacao anual do INMET."""
import sys
import time
from datetime import datetime

from etl.conexao import abrir
from etl.extrair import CSV_MG
from etl.rodar import carregar_ano


def proximo_ano(ctl) -> int | None:
    anos = sorted(int(p.name) for p in CSV_MG.iterdir() if p.is_dir())
    concluidos = {a for (a,) in ctl.execute("SELECT ano FROM dw.entrega WHERE concluida_em IS NOT NULL")}
    return next((a for a in anos if a not in concluidos), None)


def main() -> int:
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    with abrir() as dw, abrir(autocommit=True) as ctl:
        ano = proximo_ano(ctl)
        if ano is None:
            print(f"{agora} nada a entregar")
            return 0
        ctl.execute("INSERT INTO dw.entrega (ano) VALUES (%s) ON CONFLICT (ano) DO NOTHING", (ano,))
        inicio = time.perf_counter()
        try:
            arquivos, total = carregar_ano(dw, ctl, ano)
        except Exception as erro:
            print(f"{agora} entrega de {ano} falhou, tenta de novo no proximo tick: {type(erro).__name__}: {erro}")
            return 1
        ctl.execute("UPDATE dw.entrega SET concluida_em = now() WHERE ano = %s", (ano,))
        print(f"{agora} entrega de {ano} concluida: {arquivos} arquivos, {total} linhas, {time.perf_counter() - inicio:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
