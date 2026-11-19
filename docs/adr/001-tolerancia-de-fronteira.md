# 1. Station coordinates are checked against the declared state, with a 10 km tolerance

Date: 2026-11-18. Status: accepted.

## Context

Each INMET file declares a state (UF) and the station coordinates. A station whose coordinates are far from its declared state is a data error: station S122 is labelled MG and sits in Roraima. The state boundaries come from Natural Earth 1:10m admin-1 (public domain), simplified to 0.01 degree (`analise/gerar_contornos.py`).

## Decision

A station-year passes when its point is inside the boundary of the declared state or within 10 km of it (`geo.na_uf`, `geo.TOLERANCIA_FRONTEIRA_KM`). The others are flagged `em_uf = false`, stay in silver and are left out of gold.

## Evidence

All 5,747 station-year files, 2016 to 2025. With a strict inside-the-polygon test, 183 files fall outside their state: 29 stations. 25 of them sit within 5.2 km of the boundary: coastal or border stations such as Vitória, Salvador, Torres and the Rio de Janeiro fort station, pushed a few kilometres out by the simplified boundary and the coarse coast. The four beyond 10 km:

| Station | Years | Distance | Reading |
|---|---|---|---|
| A422 Abrolhos (BA) | 10 | 56 km | offshore island station |
| A895 Chapecó (SC) | 1 | 76 km | coordinates probably wrong in that file, not checked against the source |
| S122 (labelled MG) | 3 | about 2,500 km | wrong label or coordinates |
| C891 Criosfera (labelled SP) | 1 | thousands of km | Antarctica |

## Consequences

The 25 legitimate stations stay in gold. Four stations (15 station-years) are excluded. A coastal station more than 10 km from the simplified boundary would be excluded by mistake, so `python3 -m analise.estacoes_fora_da_uf` lists every exclusion and should be read after each new year of data. Revisit the tolerance if the boundaries are replaced by finer geometry.
