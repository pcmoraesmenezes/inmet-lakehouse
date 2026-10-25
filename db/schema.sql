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
);

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
