# Record validator

## Goal

Calculate an indication of completeness of an ingested record

## Mechanism

Record is ingested by pycsw, on the ingested (harmonised) result, run the validation.
Properties are evaluated by their existence resulting in a score.
some records may fail ingest and will not be validated.

| indicator | score | 
| --- | --- | 
| identifier | 10 |
| type | 5 |
| title | 25 |
| language | 5 |
| abstract | 20 |
| keywords | 10 |
| temporal_extent | 5 |
| spatial_extent | 5 |
| license (usage constraints) | 5 |
| organization | 10 |
| lineage | 5 |

## Manual

- set .env to connect to database

```
export POSTGRES_HOST=example.org
export POSTGRES_PORT=5432
export POSTGRES_DB=example
export POSTGRES_USER=example
export POSTGRES_PASSWORD=*****

```

- create table `validated`

| identifier | score | date |
| --- | --- | --- |
| aaa-bbb-ccc | 60 | 2025-01-10 |

- install requirementes.txt

```
pip install -r requirements.txt
```
- run validator

```
python validate.py
```

# INSPIRE ETS Validation in soilwise

Process of validating metadata in soilwise project according to the INSPIRE requirements is done using tool [INSPIRE Reference validator](https://inspire.ec.europa.eu/validator/home/index.html) developed and managed by the European commmission. It supports INSPIRE ETS by default and is dockerized (althought not in the newest version). In soilwise, all metadata records are stored in PostgreSQL database. Tha validation itself uses ETF Validator API, called by the python script.

### Prerequisites
1. Setup and running instance of INSPIRE ETF Validator on the server.
1. Access to the PostgreSQL database. Script is written for the schema harvest with table items, accessing columns identifier, resultobject, itemtype and insert_date.
1. Setting up the database: before the first run of validation run script `create_new_tables.sql`. It creates two new tables and adds two columns to the items table.
1. All configuration is passed via environment variables — no source edits needed. See [Environment variables](#environment-variables) below.

### Seting up INSPIRE ETF Validator via Docker

```
docker login docker.pkg.github.com 
docker-compose up -d
```

All INSPIRE Executable Test Suites shall be part of the container and are extracted to the ~/etf folder.
Then the UI is accessed from http://localhost:8090/validator/home/index.html and API from http://localhost:8090/validator/v2/.

### Validation setup

As the INSPIRE ETF validator is setup and running and database is updated according to the `create_new_tables.sql`, choose a script you want to run:
1. `validationByTestSuites.py` -- takes records from database one by one, runs the validation and waits for the validation process to end, then writes results to the database,
1. `concurrentValidation.py` -- takes records in threads, which speeds up the validation process. With too many concurrent threads, you may run out of RAM, so choose carefully. However, this shall be much faster, althought more greedy on computational power.

Script is written in a way it validates only those records, where the column `last_validation` is either empty, or with older datum than `insert_date`. Therefore, the first run of the validation validates all records in the database, but every other run validates only those that have been updated since the last validation run. That saves also some time.

Recommended usage is to run the script quite regularly, based on the expected frequency of updates.

### Environment variables

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `POSTGRES_HOST` | — | yes | Database hostname |
| `POSTGRES_PORT` | `5432` | no | Database port |
| `POSTGRES_DB` | — | yes | Database name |
| `POSTGRES_USER` | — | yes | Database user |
| `POSTGRES_PASSWORD` | — | yes | Database password |
| `ETF_URL` | `http://localhost:8090/validator` | no | Base URL of the INSPIRE ETF Validator |
| `RUN_MODE` | `sequential` | no | `sequential` or `concurrent` (Docker entrypoint only) |
| `MAX_WORKERS` | `3` | no | Thread count for concurrent mode |
| `SERVICE_MD_LABELS` | built-in list | no | JSON array of service-metadata ETS labels to use |
| `DATASET_MD_LABELS` | built-in list | no | JSON array of dataset-metadata ETS labels to use |

A `.env` file in the working directory is loaded automatically (via python-dotenv) when running scripts directly.

### Running via Docker

The Docker image is published to `ghcr.io/soilwise-he/<repository>`. Pull the latest:

```bash
docker pull ghcr.io/soilwise-he/soilwise-catalog-enrichment:latest
```

Run sequential validation (default):

```bash
docker run --rm \
  -e POSTGRES_HOST=db.example.org \
  -e POSTGRES_DB=soilwise \
  -e POSTGRES_USER=soilwise \
  -e POSTGRES_PASSWORD=secret \
  -e ETF_URL=http://etf.example.org:8090/validator \
  ghcr.io/soilwise-he/soilwise-catalog-enrichment:latest
```

Run concurrent validation:

```bash
docker run --rm \
  -e POSTGRES_HOST=db.example.org \
  -e POSTGRES_DB=soilwise \
  -e POSTGRES_USER=soilwise \
  -e POSTGRES_PASSWORD=secret \
  -e ETF_URL=http://etf.example.org:8090/validator \
  -e RUN_MODE=concurrent \
  -e MAX_WORKERS=5 \
  ghcr.io/soilwise-he/soilwise-catalog-enrichment:latest
```

Pass a `.env` file instead of individual `-e` flags:

```bash
docker run --rm --env-file .env ghcr.io/soilwise-he/soilwise-catalog-enrichment:latest
```

### What is the validation output

For every record, the table `items` is updated by the values `last_validation` and `validation_passed`. The first contains timestamp of the proccessed validation, the later is either true or false, based on the validation result. The validation reports are inserted into the table `validation_runs`. For every run are inserted values `run_id`, `metadata_identifier`, `status_passed`, `validation_timestamp`, `full_report_json` and `report_html`. Finally, for every validated metadata record values `result_id`, `run_id`, `suite_name` and `result_status` are inserted to the table `validation_suite_results`. Tables `items` and `validation_runs` may be joined by the `validation_runs.metadata_identifier` to `items.identifier` and every run is joined with test suites validation by `validation_run.run_id` to `validation_suite_results.run_id`.

### Selecting validation results

Latest status of every record that has been validated at least once:

```
SELECT 
    identifier, 
    itemtype, 
    insert_date, 
    last_validation, 
    validation_passed
FROM harvest.items
WHERE last_validation IS NOT NULL
ORDER BY last_validation DESC;
```

For comprehensive report with suite details:

```
SELECT 
    i.identifier,
    r.validation_timestamp,
    r.status_passed AS overall_passed,
    s.suite_name,
    s.result_status AS suite_result
FROM harvest.items i
JOIN harvest.validation_runs r ON i.identifier = r.metadata_identifier
JOIN harvest.validation_suite_results s ON r.run_id = s.run_id
WHERE i.last_validation IS NOT NULL
ORDER BY r.validation_timestamp DESC, s.suite_name;
```

Overall summary statistics:

```
SELECT 
    validation_passed, 
    COUNT(*) as count
FROM harvest.items
WHERE last_validation IS NOT NULL
GROUP BY validation_passed;
```