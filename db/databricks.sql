CREATE SCHEMA IF NOT EXISTS workspace.inmet;
CREATE VOLUME IF NOT EXISTS workspace.inmet.raw;

SELECT COUNT(*) FROM workspace.inmet.gold_fato_medicao_hora;
SELECT count(*) FROM workspace.inmet.gold_dim_estacao;

SELECT d.ano, COUNT(*) FROM workspace.inmet.gold_fato_medicao_hora f
JOIN workspace.inmet.gold_dim_data d USING (data_sk) 
group by d.ano 
ORDER BY d.ano