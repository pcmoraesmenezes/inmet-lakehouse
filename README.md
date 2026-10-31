# inmet-lakehouse

Ten years of hourly weather data from the automatic stations of Minas Gerais (INMET, 2016 to 2025), loaded twice: into a deliberately rigid data warehouse and into a Delta lakehouse. The goal is to measure, not to claim, what each design costs to operate and to change.

The source is public: INMET publishes one zip per year with one CSV per station. The format changed along the way, and the same station is republished with different metadata, which makes it a good test for both designs.

## The two architectures

**Rigid warehouse** (`etl/`, `db/schema.sql`, `docker-compose.yml`): PostgreSQL 16, a fixed schema, and a batch ETL that deletes and reloads one station-year at a time. A cron job inside a container delivers one year every two minutes to simulate the yearly publication. Every run is recorded in `dw.carga` and every delivery in `dw.entrega`.

**Lakehouse** (`databricks/`): Delta tables on Databricks Free Edition, in medallion layers.

| Layer | Table | Content |
|---|---|---|
| Raw | volume `workspace.inmet.raw` | Original zips, with a manifest of sha256, size and `Last-Modified` per download |
| Bronze | `bronze_csv` | Every line of every MG CSV as text, plus file, year and ingestion time. 5,820,783 lines |
| Silver | `silver_estacao_ano`, `silver_medicao` | Typed columns, one UTC timestamp for all three file layouts, rows with no measurement dropped and counted. 5,398,086 rows |
| Gold | `gold_dim_estacao`, `gold_dim_data`, `gold_dim_hora`, `gold_fato_medicao_hora` | Star schema. The station dimension is versioned when position moves more than 100 m or altitude more than 50 m: 86 rows for 69 stations. The fact has 5,393,421 rows |

Each layer reconciles against the previous one by year (row counts, duplicates, per-column non-null counts) and stops with an error when the numbers disagree.

## What the data showed

- Three file layouts: 2016 to 2018 (`2016-01-01`, `00:00`, missing as `-9999`), 2019 (`2019/01/01`, `0000 UTC`, missing as an empty field), 2020 to 2025 (same as 2019, radiation unit spelled differently). The bronze layer absorbs all three unchanged. The rigid ETL failed on the first 2019 file.
- Station S122 is labelled MG but sits at latitude 3.4 and longitude -59.8. It stays in silver with `em_mg = false` and is filtered out in gold.
- INMET revised the altitude of 56 of 67 stations between 2018 and 2019 (median 8 m, largest 381 m), and the position of 9 stations by more than 1 km. A station dimension without history silently rewrites the past.
- Solar radiation is missing in 94% of night hours by design. Apart from radiation, missing values range from 3.5% (2019) to 17.2% (2021).
- 286 radiation values exceed 5,000 kJ/m2 per hour, above the top-of-atmosphere limit, and are set to null.

## Measured comparison

Same operations on both sides, on a throwaway copy of the fact table. PostgreSQL ran in a local container. The lakehouse ran on Databricks Free Edition serverless compute. One run each, three for the queries, so read these as orders of magnitude, not as a hardware benchmark. Scripts: `analise/medir_dw.py`, `analise/medir_schema.py`, `databricks/06_medir_lakehouse.py`.

| Operation | PostgreSQL | Lakehouse |
|---|---|---|
| Fact table size | 845 MB (620 MB table, 225 MB index), 5.8M rows | 90 MB, 5.39M rows |
| Query, 1 day, all stations | 100 to 120 ms (full scan) | 0.84 to 0.92 s |
| Query, 1 day, 1 station | 0.1 ms | 0.78 s |
| Reprocess one station-year (A502, 2025) | 8,760 rows in 0.15 to 0.20 s | 8,710 rows in 5.06 s |
| Reprocess one whole year | not a unit of the ETL | 531,711 rows in 2.69 s |
| Delete one day of one station | 1.3 ms | 1.6 s |
| Add a nullable column | 0.00 s | 1.29 s |
| Add a `NOT NULL DEFAULT` column | 0.00 s | not supported by Delta |
| Change a column type, with a reader 1 s later | 6.6 s, reader waited 5.5 s | in-place change refused; rewrite 6.44 s, reader waited 1.18 s |
| Backfill the new column on every row | 23.6 s, table doubles until `VACUUM` | 4.70 s |
| `CHECK (precip_mm >= 0)` | 0.5 s, passes | fails: 217,258 rows violate it |

At this scale, 5 million rows and one user, PostgreSQL wins on point latency and the lakehouse wins on storage, bulk rewrites and non-blocking reads. The more important costs are structural: a format change, a partial load, and a dimension that forgets history. The size after the backfill is the current snapshot only; old Delta files stay in storage until a `VACUUM`, which was not measured. The row counts differ slightly because PostgreSQL also keeps rows with no measurement and station S122.

The failed `CHECK` is a semantic difference, not a data problem. There is no negative precipitation in the CSVs. The 217,258 rows are exactly the rows with a null `precip_mm`, so Delta counts a null as a violation where PostgreSQL does not. The portable form is `precip_mm IS NULL OR precip_mm >= 0`.

## Running it

Rigid warehouse (Docker and `uv`). The ETL reads `PG_USER`, `PG_PASSWORD` and optionally `PG_HOST`, `PG_PORT` (default 5440) and `PG_DB` (default `inmet_dw`) from the environment; `.env.example` has the two required ones.

```
cp .env.example .env
docker compose up -d postgres
docker exec -i inmet_pg sh -c 'psql -U "$POSTGRES_USER" -d inmet_dw' < db/schema.sql
uv run --env-file .env python -m etl.rodar --ano 2016
```

`docker compose up -d etl` starts the simulation: a container that delivers one year every two minutes into a second database, `inmet_sim`, created with `db/schema.sql` plus the delivery ledger in `db/simulacao.sql`. Raw CSVs go in `work/csv_mg/<year>/` and are not versioned.

Lakehouse: add the repository as a Git folder in Databricks, download the zips into the volume with `ingest/baixar_inmet.py`, then run `databricks/01_extrair_mg.py`, `02_bronze.py`, `04_prata.py`, `05_ouro.py` and, to repeat the comparison, `06_medir_lakehouse.py`. `03_analise_bronze.py` is the exploratory step on the bronze layer. Every layer is safe to rerun: loads replace one year at a time.

## Limitations

- The station surrogate key is the row position in the sorted dimension, which is rewritten on every load. Adding a version to one early station changes 84 of the 86 keys, so the fact table is rebuilt in full on every run and an incremental load would corrupt old years.
- Every run reprocesses all years. The manifest sha256 is not stored in bronze, so an unchanged year cannot be skipped.
- There is no scheduled job, no run log in the lakehouse (the PostgreSQL side has one), no automated tests, and the catalog and schema names are fixed in the code.
- The quality checks run after the write, not before.
