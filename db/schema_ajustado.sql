CREATE SCHEMA dw;

CREATE TABLE dw.estacao (
    cod            text PRIMARY KEY,
    nome           text NOT NULL,
    uf             char(2) NOT NULL,
    regiao         text,
    latitude       double precision,
    longitude      double precision,
    altitude       real,
    data_fundacao  date
);

CREATE TABLE dw.medicao (
    cod                 text NOT NULL REFERENCES dw.estacao (cod),
    data_hora_utc       timestamp NOT NULL,
    precip_mm           real,
    pressao_mb          real,
    pressao_max_mb      real,
    pressao_min_mb      real,
    radiacao_kjm2       real,
    temp_ar_c           real,
    temp_orvalho_c      real,
    temp_max_c          real,
    temp_min_c          real,
    temp_orvalho_max_c  real,
    temp_orvalho_min_c  real,
    umid_max_pct        real,
    umid_min_pct        real,
    umid_pct            real,
    vento_dir_gr        real,
    vento_rajada_ms     real,
    vento_vel_ms        real,
    PRIMARY KEY (cod, data_hora_utc)
) PARTITION BY RANGE (data_hora_utc);

CREATE TABLE dw.medicao_2016 PARTITION OF dw.medicao FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');
CREATE TABLE dw.medicao_2017 PARTITION OF dw.medicao FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');
CREATE TABLE dw.medicao_2018 PARTITION OF dw.medicao FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');
CREATE TABLE dw.medicao_2019 PARTITION OF dw.medicao FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE dw.medicao_2020 PARTITION OF dw.medicao FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE dw.medicao_2021 PARTITION OF dw.medicao FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE dw.medicao_2022 PARTITION OF dw.medicao FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE dw.medicao_2023 PARTITION OF dw.medicao FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE dw.medicao_2024 PARTITION OF dw.medicao FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE dw.medicao_2025 PARTITION OF dw.medicao FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE dw.medicao_outros PARTITION OF dw.medicao DEFAULT;

-- A carga grava uma estação por vez, então só blocos vizinhos pequenos cobrem uma faixa curta de datas.
CREATE INDEX medicao_data_brin ON dw.medicao USING BRIN (data_hora_utc) WITH (pages_per_range = 4);

CREATE TABLE dw.carga (
    id       bigserial PRIMARY KEY,
    ano      smallint NOT NULL,
    arquivo  text NOT NULL,
    linhas   integer,
    inicio   timestamptz NOT NULL DEFAULT now(),
    fim      timestamptz,
    status   text NOT NULL DEFAULT 'rodando' CHECK (status IN ('rodando', 'ok', 'erro')),
    erro     text
);
