CREATE TABLE dw.entrega (
    ano           smallint PRIMARY KEY,
    entregue_em   timestamptz NOT NULL DEFAULT now(),
    concluida_em  timestamptz
);
