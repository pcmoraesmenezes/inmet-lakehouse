"""Figuras e frases da analise da bronze, cada degrau com uma pergunta, um grafico e uma frase-resposta."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon

from analise import geo
from etl.extrair import COD_NOME_DO_ARQUIVO  # noqa: F401
from etl.transformar import HORA_DIA_UTC, HORA_NOITE_UTC  # noqa: F401

NOMES = {
    "c02": "Chuva (mm)",
    "c03": "Pressão na estação (mB)",
    "c04": "Pressão máxima na hora (mB)",
    "c05": "Pressão mínima na hora (mB)",
    "c06": "Radiação solar (kJ/m²)",
    "c07": "Temperatura do ar (°C)",
    "c08": "Ponto de orvalho (°C)",
    "c09": "Temperatura máxima na hora (°C)",
    "c10": "Temperatura mínima na hora (°C)",
    "c11": "Orvalho máximo na hora (°C)",
    "c12": "Orvalho mínimo na hora (°C)",
    "c13": "Umidade máxima na hora (%)",
    "c14": "Umidade mínima na hora (%)",
    "c15": "Umidade do ar (%)",
    "c16": "Direção do vento (graus)",
    "c17": "Rajada de vento (m/s)",
    "c18": "Velocidade do vento (m/s)",
}
MEDIDAS = list(NOMES)
ROTULO_AUSENTE = {**NOMES, "c06": "Radiação solar de dia (kJ/m²)", "c06n": "Radiação solar de noite (kJ/m²)"}
TETO_COR_AUSENTE = 30
COR = {"neutro": "#8e99a8", "alerta": "#c8372d", "linha": "#2f6f9f", "fundo": "#eef1f5",
       "borda": "#b6bec9", "texto": "#2b2f36", "suave": "#5d6673"}
LIMITE_DESLOCAMENTO_KM = 1
COBERTURA_MINIMA = 0.8
DESVIO_TEMPERATURA_C = 2
GRADIENTE_PADRAO_C_POR_KM = 6.5



def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def gabarito_ausentes(ausentes: pd.DataFrame) -> dict[int, float]:
    medidas = ausentes[~ausentes.variavel.isin(["c06", "c06n"])]
    por_ano = medidas.groupby("ano")[["ausentes", "linhas"]].sum()
    return {int(a): round(float(100 * r.ausentes / r.linhas), 1) for a, r in por_ano.iterrows()}


def ultima_posicao(est: pd.DataFrame) -> pd.DataFrame:
    return est.sort_values("ano").groupby("cod", as_index=False).last()


def deslocamentos(est: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for cod, g in est.dropna(subset=["lat", "lon"]).sort_values("ano").groupby("cod"):
        a, b = g.iloc[0], g.iloc[-1]
        linhas.append(dict(cod=cod, nome=b.nome, ano0=int(a.ano), ano1=int(b.ano), lat0=a.lat, lon0=a.lon,
                           lat1=b.lat, lon1=b.lon, km=geo.distancia_km(a.lat, a.lon, b.lat, b.lon)))
    return pd.DataFrame(linhas)


def _folha(titulo: str, ficha: str, tamanho: tuple[float, float]):
    fig = plt.figure(figsize=tamanho, facecolor="white")
    fig.text(0.03, 0.965, titulo, fontsize=17, weight="bold", color=COR["texto"], va="top")
    fig.text(0.03, 0.915, ficha, fontsize=11, color=COR["suave"], va="top")
    return fig


def _mapa_de_mg(ax, aneis) -> None:
    for anel in aneis:
        ax.add_patch(Polygon(anel, closed=True, facecolor=COR["fundo"], edgecolor=COR["borda"], linewidth=1.2))
    lons, lats = zip(*[p for anel in aneis for p in anel])
    ax.set_xlim(min(lons) - 0.3, max(lons) + 0.3)
    ax.set_ylim(min(lats) - 0.3, max(lats) + 0.3)
    ax.set_aspect(1 / np.cos(np.radians(np.mean([min(lats), max(lats)]))))
    ax.axis("off")


def figura_posicoes(est: pd.DataFrame, caminho: str) -> str:
    aneis = geo.carregar_contorno()
    pos = ultima_posicao(est).dropna(subset=["lat", "lon"])
    pos = pos.assign(em_mg=[geo.dentro(lo, la, aneis) for la, lo in zip(pos.lat, pos.lon)])
    dentro, fora = pos[pos.em_mg], pos[~pos.em_mg]
    anos = f"{int(est.ano.min())} a {int(est.ano.max())}"
    fig = _folha("Onde ficam as estações do INMET em Minas Gerais?",
                 f"{len(pos)} estações automáticas, cada uma na posição do seu ano mais recente ({anos})", (10, 8.6))
    ax = fig.add_axes([0.03, 0.04, 0.94, 0.80])
    _mapa_de_mg(ax, aneis)
    ax.scatter(dentro.lon, dentro.lat, s=55, color=COR["linha"], edgecolor="white", linewidth=0.8, zorder=3)
    if len(fora):
        r = fora.iloc[0]
        ax.text(0.0, 0.0, f"Fora do mapa: {r.cod} {r.nome}, coordenadas fora de MG (lat {r.lat:.1f}, lon {r.lon:.1f})",
                transform=ax.transAxes, fontsize=11, color=COR["alerta"], va="bottom")
    fig.savefig(caminho, dpi=150, facecolor="white")
    plt.close(fig)
    return f"{len(dentro)} de {len(pos)} estações têm coordenadas dentro de MG; {len(fora)} tem coordenadas fora de MG."


def figura_deslocamentos(est: pd.DataFrame, caminho: str) -> str:
    aneis = geo.carregar_contorno()
    desl = deslocamentos(est)
    moveram = desl[desl.km > LIMITE_DESLOCAMENTO_KM].sort_values("km", ascending=False)
    em_mg = pd.Series([geo.dentro(lo, la, aneis) for la, lo in zip(desl.lat1, desl.lon1)], index=desl.index)
    ficaram = desl[(desl.km <= LIMITE_DESLOCAMENTO_KM) & em_mg]
    fig = _folha("Quais estações mudaram de lugar?",
                 f"{len(desl)} estações; seta do primeiro ao último ano de cada uma, só as que se deslocaram mais de {LIMITE_DESLOCAMENTO_KM} km",
                 (10, 8.6))
    ax = fig.add_axes([0.03, 0.04, 0.94, 0.80])
    _mapa_de_mg(ax, aneis)
    ax.scatter(ficaram.lon1, ficaram.lat1, s=30, color=COR["neutro"], zorder=2)
    for r in moveram.itertuples():
        ax.annotate("", xy=(r.lon1, r.lat1), xytext=(r.lon0, r.lat0), zorder=4,
                    arrowprops=dict(arrowstyle="-|>", color=COR["alerta"], lw=1.8, shrinkA=0, shrinkB=0))
        ax.text(r.lon1 + 0.12, r.lat1 + 0.08, f"{r.cod}  {r.km:.0f} km", fontsize=10.5, color=COR["alerta"], zorder=5)
    fig.savefig(caminho, dpi=150, facecolor="white")
    plt.close(fig)
    if moveram.empty:
        return f"Nenhuma das {len(desl)} estações mudou mais de {LIMITE_DESLOCAMENTO_KM} km de lugar."
    maior = moveram.iloc[0]
    return (f"{len(moveram)} de {len(desl)} estações mudaram mais de {LIMITE_DESLOCAMENTO_KM} km de lugar; "
            f"a maior mudança foi de {maior.km:.0f} km ({maior.cod}).")


def _percentual_por_variavel(ausentes: pd.DataFrame) -> pd.DataFrame:
    tabela = ausentes.assign(pct=100 * ausentes.ausentes / ausentes.linhas)
    return tabela.pivot(index="variavel", columns="ano", values="pct")


def figura_ausentes(ausentes: pd.DataFrame, caminho: str) -> str:
    pct = _percentual_por_variavel(ausentes)
    total = ausentes.groupby("variavel")[["ausentes", "linhas"]].sum()
    geral = (100 * total.ausentes / total.linhas).sort_values(ascending=False)
    pct = pct.loc[geral.index]
    horas = int(ausentes.groupby("ano").linhas.max().sum())
    anos = list(pct.columns)
    fig = _folha("Quanto de cada medida falta, ano a ano?",
                 f"{milhar(horas)} horas de estação em MG, {anos[0]} a {anos[-1]}; % das horas sem medida (a radiação é contada separada, de dia e de noite)", (12.5, 9))
    ax = fig.add_axes([0.30, 0.06, 0.66, 0.78])
    teto = TETO_COR_AUSENTE
    ax.imshow(pct.values, cmap="Reds", vmin=0, vmax=teto, aspect="auto")
    ax.set_xticks(range(len(anos)), anos, fontsize=11)
    ax.set_yticks(range(len(pct)), [ROTULO_AUSENTE[v] for v in pct.index], fontsize=11)
    ax.xaxis.tick_top()
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    for i in range(pct.shape[0]):
        for j in range(pct.shape[1]):
            v = pct.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=10.5,
                    color="white" if v > 0.6 * teto else COR["texto"])
    fig.savefig(caminho, dpi=150, facecolor="white")
    plt.close(fig)
    noite = geral["c06n"]
    comuns = geral.drop("c06n")
    mais, menos = comuns.index[0], comuns.index[-1]
    return (f"A radiação fica sem medida em {noite:.0f}% das horas da noite; fora isso, a medida que mais falta é "
            f"{ROTULO_AUSENTE[mais]} ({comuns[mais]:.0f}% das horas) e a que menos falta é {ROTULO_AUSENTE[menos]} ({comuns[menos]:.0f}%).")


def figura_valores_tipicos(faixas: pd.DataFrame, caminho: str) -> str:
    anos = sorted(faixas.ano.unique())
    fig = _folha("O valor típico de cada medida mudou ao longo dos anos?",
                 f"mediana de cada ano e faixa com 98% dos valores, só horas com medida; MG, {anos[0]} a {anos[-1]}; "
                 "tracejado: 2019, quando o formato do arquivo mudou", (15, 10))
    saltos = []
    for k, cod in enumerate(MEDIDAS):
        ax = fig.add_axes([0.04 + (k % 4) * 0.24, 0.74 - (k // 4) * 0.175, 0.20, 0.11])
        g = faixas[faixas.variavel == cod].sort_values("ano")
        ax.fill_between(g.ano, g.p01, g.p99, color=COR["fundo"], edgecolor="none")
        ax.plot(g.ano, g.mediana, color=COR["linha"], linewidth=2, marker="o", markersize=3.5)
        ax.axvline(2018.5, color=COR["borda"], linestyle="--", linewidth=1)
        ax.set_title(NOMES[cod], fontsize=11, loc="left", color=COR["texto"])
        ax.set_xticks([anos[0], 2019, anos[-1]])
        ax.tick_params(labelsize=9, length=2)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        amplitude = float((g.p99 - g.p01).mean())
        saltos.append((float(g.mediana.max() - g.mediana.min()) / amplitude if amplitude else 0.0, cod, g))
    fig.savefig(caminho, dpi=150, facecolor="white")
    plt.close(fig)
    salto, cod, g = max(saltos, key=lambda s: s[0])
    menor, maior = g.loc[g.mediana.idxmin()], g.loc[g.mediana.idxmax()]
    return (f"A mediana de cada medida varia no máximo {salto:.0%} da sua faixa de valores entre os anos; "
            f"o maior caso é {NOMES[cod]}, de {menor.mediana:.1f} em {int(menor.ano)} a {maior.mediana:.1f} em {int(maior.ano)}.")


def figura_altitude_temperatura(temp: pd.DataFrame, caminho: str) -> str:
    ano = int(temp.ano.max())
    base = temp[(temp.ano == ano) & (temp.cobertura >= COBERTURA_MINIMA)].dropna(subset=["alt", "temp_media"])
    angular, linear = np.polyfit(base.alt, base.temp_media, 1)
    residuo = base.temp_media - (angular * base.alt + linear)
    fora = base[residuo.abs() > DESVIO_TEMPERATURA_C]
    dentro = base.drop(fora.index)
    por_km = -angular * 1000
    fig = _folha("A temperatura cai com a altitude como a física espera?",
                 f"{len(base)} estações em {ano}; temperatura média do ano contra a altitude; "
                 f"só estações com ao menos {COBERTURA_MINIMA:.0%} das horas medidas", (10, 8))
    ax = fig.add_axes([0.10, 0.10, 0.86, 0.74])
    x = np.array([base.alt.min(), base.alt.max()])
    ax.plot(x, angular * x + linear, color=COR["linha"], linewidth=2, label=f"observado: {por_km:.1f} °C por 1000 m")
    ax.plot(x, (angular * x.mean() + linear) - (GRADIENTE_PADRAO_C_POR_KM / 1000) * (x - x.mean()), color=COR["borda"],
            linewidth=2, linestyle="--", label=f"esperado: {GRADIENTE_PADRAO_C_POR_KM:.1f} °C por 1000 m")
    ax.scatter(dentro.alt, dentro.temp_media, s=50, color=COR["neutro"], zorder=3)
    ax.scatter(fora.alt, fora.temp_media, s=60, color=COR["alerta"], zorder=4)
    for r in fora.itertuples():
        ax.annotate(r.cod, (r.alt, r.temp_media), xytext=(6, 5), textcoords="offset points", fontsize=10.5, color=COR["alerta"])
    ax.set_xlabel("Altitude (m)", fontsize=12)
    ax.set_ylabel("Temperatura média do ano (°C)", fontsize=12)
    ax.legend(frameon=False, fontsize=11, loc="upper right")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.savefig(caminho, dpi=150, facecolor="white")
    plt.close(fig)
    return (f"A temperatura cai {por_km:.1f} °C a cada 1000 m (a atmosfera padrão cai {GRADIENTE_PADRAO_C_POR_KM:.1f}); "
            f"{len(fora)} estações ficam a mais de {DESVIO_TEMPERATURA_C} °C da tendência.")
