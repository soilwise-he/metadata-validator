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

### Prerequisities
1. Setup and running instance of INSPIRE ETF Validator on the server. 
1. Access to the PostgreSQL database. Script is written for the schema harvest with table items, accessing columns identifier, resultobject, itemtype and insert_date. 
1. Setting up the database: before the first run of validation run script `create_new_trables.sql`. It creates two new tables and adds two columns to the items table.
1. Setting up the script variables: folder validationINSPIRE contains scripts `getETS.py`, `validationByTestSuites.py` and `concurrentValidation.py`. First script returs the list of all available Executable Test Suites in the validator. Other two arefor validation itself. In the first part of each script, configure database connection credentials and list of desired Test Suites (there are predefined tests for dataset metadata and service metadata validation, which are used in the UI of the validator for dataset/series and network services metadata validation). In the concurrent validation script there must be also set up the number of threadas to work. Be careful about this, with too many workers, yu get out of RAM and BaseX will throw 500 on validation requests.

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

Recommended usage is to run the script quite regulary, based on the expected frequency of updates.

### What is the validation output

For every record, the table `items` is updated by the values `last_validation` and `validation_passed`. The first contains timestamp of the proccessed validation, tha later is either true or false, based on the validation result. The validation reports are inserted into the table `validation_runs`. For every run are inserted values `run_id`, `metadata_identifier`, `status_passed`, `validation_timestamp`, `full_report_json` and `report_html`. Finally, for every validated metadata record values `result_id`, `run_id`, `suite_name` and `result_status` are inserted to the table `validation _runs`. Tables `items` and `validation_runs` may be joined by the `validation_runs.metadata_identifier` to `items.identifier` and every run is joined with test suites validation by `validation_run.run_id` to `validation_suite_reults.run_id`.

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