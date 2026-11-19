-- Gerado por analise/consultas.py (lakehouse, MG, 2024). Não editar: a fonte é db/consultas.sql.

SET TIME ZONE 'UTC';

 SELECT estacao_sk, cod, ano_inicio, ano_fim
  FROM workspace.inmet.gold_dim_estacao
  WHERE cod = 'A502'
  ORDER BY ano_inicio;



-- Q1: As 20 estações com maior radiação média em um ano | consumidor: analista de recurso
SELECT e.cod, e.nome, e.uf,
       AVG(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_media_kjm2
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-01-01' AND m.data_hora_utc < '2025-01-01' AND e.uf = 'MG'
GROUP BY e.cod, e.nome, e.uf
ORDER BY radiacao_media_kjm2 DESC
LIMIT 20;

-- Q2: Vento médio por estação e mês, em um ano | consumidor: analista de recurso
SELECT e.cod, EXTRACT(MONTH FROM m.data_hora_utc) AS mes, AVG(m.vento_vel_ms) AS vento_medio_ms
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-01-01' AND m.data_hora_utc < '2025-01-01' AND e.uf = 'MG'
GROUP BY e.cod, EXTRACT(MONTH FROM m.data_hora_utc)
ORDER BY e.cod, mes;

-- Q3: Radiação e vento médios por estação e dia, em 30 dias | consumidor: analista de recurso
SELECT e.cod, CAST(m.data_hora_utc AS DATE) AS dia,
       AVG(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_media_kjm2,
       AVG(m.vento_vel_ms) AS vento_medio_ms
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-06-01' AND m.data_hora_utc < '2024-07-01' AND e.uf = 'MG'
GROUP BY e.cod, CAST(m.data_hora_utc AS DATE)
ORDER BY e.cod, dia;

-- Q4: Série horária de uma estação em um mês | consumidor: analista de recurso
SELECT m.data_hora_utc,
       CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END AS radiacao_kjm2,
       m.vento_vel_ms, m.temp_ar_c
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE e.cod = 'A502' AND m.data_hora_utc >= '2024-06-01' AND m.data_hora_utc < '2024-07-01'
ORDER BY m.data_hora_utc;

-- Q5: Relatório de um mês por UF, com estações, horas com vento, radiação e vento médios | consumidor: operações e finanças
SELECT e.uf, COUNT(DISTINCT e.cod) AS estacoes, COUNT(m.vento_vel_ms) AS horas_com_vento,
       AVG(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_media_kjm2,
       AVG(m.vento_vel_ms) AS vento_medio_ms
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-06-01' AND m.data_hora_utc < '2024-07-01' AND e.uf = 'MG'
GROUP BY e.uf
ORDER BY e.uf;

-- Q6: Horas com medida de vento e de radiação por estação e mês, em um ano | consumidor: operações e finanças
SELECT e.cod, EXTRACT(MONTH FROM m.data_hora_utc) AS mes,
       COUNT(m.vento_vel_ms) AS horas_com_vento,
       COUNT(CASE WHEN m.radiacao_kjm2 <= 5000 THEN 1 END) AS horas_com_radiacao
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-01-01' AND m.data_hora_utc < '2025-01-01' AND e.uf = 'MG'
GROUP BY e.cod, EXTRACT(MONTH FROM m.data_hora_utc)
ORDER BY e.cod, mes;

-- Q7: Tabela de atributos diária por estação, em um ano | consumidor: ciência de dados
SELECT e.cod, CAST(m.data_hora_utc AS DATE) AS dia,
       AVG(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_media,
       MAX(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_max,
       MIN(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_min,
       AVG(m.vento_vel_ms) AS vento_medio, MAX(m.vento_vel_ms) AS vento_max, MIN(m.vento_vel_ms) AS vento_min,
       AVG(m.temp_ar_c) AS temp_media, MAX(m.temp_ar_c) AS temp_max, MIN(m.temp_ar_c) AS temp_min
FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
WHERE m.data_hora_utc >= '2024-01-01' AND m.data_hora_utc < '2025-01-01' AND e.uf = 'MG'
GROUP BY e.cod, CAST(m.data_hora_utc AS DATE)
ORDER BY e.cod, dia;

-- Q8: Anomalia da radiação média mensal de cada estação contra o mesmo mês nos outros anos | consumidor: ciência de dados
WITH mensal AS (
    SELECT e.cod, EXTRACT(YEAR FROM m.data_hora_utc) AS ano, EXTRACT(MONTH FROM m.data_hora_utc) AS mes,
           AVG(CASE WHEN m.radiacao_kjm2 <= 5000 THEN m.radiacao_kjm2 END) AS radiacao_media
    FROM workspace.inmet.gold_fato_medicao_hora m JOIN workspace.inmet.gold_dim_estacao e ON e.estacao_sk = m.estacao_sk
    WHERE 1 = 1 AND e.uf = 'MG'
    GROUP BY e.cod, EXTRACT(YEAR FROM m.data_hora_utc), EXTRACT(MONTH FROM m.data_hora_utc)
)
SELECT cod, ano, mes, radiacao_media,
       radiacao_media - (SUM(radiacao_media) OVER (PARTITION BY cod, mes) - radiacao_media)
           / NULLIF(COUNT(radiacao_media) OVER (PARTITION BY cod, mes) - 1, 0) AS anomalia
FROM mensal
ORDER BY cod, ano, mes;
