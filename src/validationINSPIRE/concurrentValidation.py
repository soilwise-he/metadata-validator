import psycopg2
import requests
import time
import json
import zipfile
import io
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from urllib3 import request
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
def _load_label_list(env_var, default):
    raw = os.environ.get(env_var)
    if not raw:
        return default
    try:
        value = json.loads(raw)
        if not isinstance(value, list):
            raise ValueError("expected a JSON array")
        return value
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {env_var} must be a JSON array of strings. {exc}")
        sys.exit(1)

_required = {
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    print(f"Error: required environment variables not set: {', '.join(_missing)}")
    sys.exit(1)

DB_CONFIG = {
    "dbname": _required["POSTGRES_DB"],
    "user": _required["POSTGRES_USER"],
    "password": _required["POSTGRES_PASSWORD"],
    "host": _required["POSTGRES_HOST"],
    "port": int(os.environ.get("POSTGRES_PORT", "5432"))
}
ETF_URL = os.environ.get("ETF_URL", "http://localhost:8090/validator")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "3"))  # Number of concurrent validations to run at once

_DEFAULT_SERVICE_MD = ["Common Requirements for ISO/TC 19139:2007 based INSPIRE metadata records.",
                       "Conformance Class 3: INSPIRE Spatial Data Service baseline metadata.",
                       "Conformance Class 4: INSPIRE Network Services metadata.",
                       "Conformance Class 4b: INSPIRE Network Services metadata for Monitoring."]
_DEFAULT_DATASET_MD = ["Common Requirements for ISO/TC 19139:2007 based INSPIRE metadata records.",
                       "Conformance Class 1: INSPIRE data sets and data set series baseline metadata.",
                       "Conformance Class 2: INSPIRE data sets and data set series interoperability metadata.",
                       "Conformance Class 2b: INSPIRE data sets and data set series metadata for Monitoring",
                       "Conformance Class 8: INSPIRE data sets and data set series linked service metadata"]
SERVICE_MD = _load_label_list("SERVICE_MD_LABELS", _DEFAULT_SERVICE_MD)
DATASET_MD = _load_label_list("DATASET_MD_LABELS", _DEFAULT_DATASET_MD)

def get_suite_ids(target_labels):
    """Fetches ETS IDs based on the labels provided."""
    try:
        r = requests.get(f"{ETF_URL}/v2/ExecutableTestSuites.json")
        r.raise_for_status()
        all_suites = r.json()['EtfItemCollection']['executableTestSuites']['ExecutableTestSuite']
        return [s['id'] for s in all_suites if s.get('label') in target_labels]
    except Exception as e:
        print(f"Error fetching suites: {e}")
        return []


def create_test_object(identifier, xml_content):
    """Wraps XML in a ZIP buffer with a forced .xml extension."""
    url = f"{ETF_URL}/v2/TestObjects?action=upload"
    clean_id = str(identifier).split('/')[-1].split('\\')[-1]
    filename_inside_zip = f"{clean_id}.xml"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        content = xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content
        zip_file.writestr(filename_inside_zip, content)

    zip_buffer.seek(0)
    files = {'file': ('upload.zip', zip_buffer, 'application/zip')}
    data = {'label': f"Obj_{clean_id}", 'testObjectTypes': 'ReferencedResource'}

    response = requests.post(url, files=files, data=data)
    response.raise_for_status()
    return response.json()['testObject']['id']

def analyze_results(data):
    collection = data.get("EtfItemCollection", {})
    referenced_items = collection.get("referencedItems", {})

    # --- 1. Map ETS IDs to Labels ---
    # Example: "EID59692c11..." -> "Common Requirements..."
    ets_label_map = {}
    ets_list = referenced_items.get("executableTestSuites", {}).get("ExecutableTestSuite", [])
    if isinstance(ets_list, dict): ets_list = [ets_list]
    for ets in ets_list:
        ets_label_map[ets['id']] = ets.get('label', 'Unknown Suite')

    # --- 2. Create the Bridge (Result ID -> Label) ---
    # We look at testTasks to see which Result ID belongs to which ETS ID
    result_to_label = {}
    test_run = collection.get("testRuns", {}).get("TestRun", {})
    tasks = test_run.get("testTasks", {}).get("TestTask", [])
    if isinstance(tasks, dict): tasks = [tasks]

    for task in tasks:
        ets_id = task.get("executableTestSuite", {}).get("ref")
        result_id = task.get("testTaskResult", {}).get("ref")

        if ets_id in ets_label_map and result_id:
            result_to_label[result_id] = ets_label_map[ets_id]

    # --- 3. Extract Statuses using the Bridge ---
    # Path: referencedItems -> testTaskResults -> TestTaskResult
    task_results = referenced_items.get("testTaskResults", {}).get("TestTaskResult", [])
    if isinstance(task_results, dict): task_results = [task_results]

    detailed_results = []

    for task_res in task_results:
        # Identify which suite this task result belongs to
        res_id = task_res.get("id")
        suite_name = result_to_label.get(res_id, "Unknown Test Suite")

        # Get the status from the module level
        module_results_wrapper = task_res.get("testModuleResults", {})
        module_results = module_results_wrapper.get("TestModuleResult", [])
        if isinstance(module_results, dict): module_results = [module_results]

        for module in module_results:
            status = module.get("status", "UNKNOWN")

            # We add it to the list (handling multiple modules in one suite if they exist)
            detailed_results.append({
                "name": suite_name,
                "result": status
            })

    return detailed_results


def auto_cleanup_stuck_records():
    """Removes history entries that lack a terminal status to prevent 'stuck' IDs."""
    print("Running database health check...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # REMOVES: Runs where status is missing in JSON (crashed runs)
        # These are usually the records that show up as NULL in harvest.items
        cur.execute("""
            DELETE FROM harvest.validation_runs
            WHERE (full_report_json->'EtfItemCollection'->'testRuns'->'TestRun'->>'status') IS NULL;
        """)
        deleted = cur.rowcount

        conn.commit()
        if deleted > 0:
            print(f"Cleaned up {deleted} 'zombie' validation records.")
    except Exception as e:
        print(f"Health check warning: {e}")
    finally:
        conn.close()

def run_validation(test_object_id, suite_ids):
    """Triggers validation and returns the full summary data."""
    url = f"{ETF_URL}/v2/TestRuns"
    payload = {
        "label": f"Run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "executableTestSuiteIds": suite_ids,
        "arguments": {"files_to_test": ".*", "tests_to_execute": ".*"},
        "testObject": {"id": test_object_id}
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    run_id = response.json()['EtfItemCollection']['testRuns']['TestRun']['id']

    while True:
        time.sleep(5)
        response = requests.get(f"{ETF_URL}/v2/TestRuns/{run_id}.json")
        #response_html = request.get(f"{ETF_URL}/v2/TestRuns/{run_id}.html")

        data_json = response.json()

        current_status = data_json.get("EtfItemCollection", {}).get("testRuns", {}).get("TestRun", {}).get("status")

        if current_status in ["RUNNING", "UNDEFINED", "STARTING"]:
            continue

        # Terminal state reached
        passed = (current_status in  ["PASSED", "PASSED_MANUAL"])

        html_report = ""
        try:
            html_resp = requests.get(f"{ETF_URL}/v2/TestRuns/{run_id}.html")
            if html_resp.status_code == 200:
                html_report = html_resp.text
        except Exception as e:
            print(f"Warning: Could not fetch HTML report: {e}")

        # Always analyze results to get the detailed suite array
        suites_results = analyze_results(data_json)

        return passed, data_json, suites_results, html_report

def process_single_record(record, service_suite_ids, dataset_suite_ids):
    """Handles the full lifecycle for one metadata record."""
    identifier, xml_data, item_type = record
    print(f"Starting: {identifier} with metadata type {item_type}")

    # Establish its own connection for thread safety
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # 1. Register Object
        obj_id = create_test_object(identifier, xml_data)

        # 2. Select Suites
        suites = service_suite_ids if item_type == "service" else dataset_suite_ids
        if not suites:
            return f"Skipped {identifier}: No suites"

        # 3. Run and Wait
        passed, report, suite_array, html_report = run_validation(obj_id, suites)
        now = datetime.now()
        print(f"Run {obj_id} Finished. Overall Pass: {passed}. Metadata type: {item_type}")
        for s in suite_array:
            print(f"  > Suite: {s['name']} -> {s['result']}")

        # 4. Save to Database
        insert_run = """
            INSERT INTO harvest.validation_runs
            (metadata_identifier, status_passed, validation_timestamp, full_report_json, result_html)
            VALUES (%s, %s, %s, %s, %s) RETURNING run_id;
        """
        cur.execute(insert_run, (identifier, passed, now, json.dumps(report), html_report))
        new_run_id = cur.fetchone()[0]

        if suite_array:
            insert_suite = "INSERT INTO harvest.validation_suite_results (run_id, suite_name, result_status) VALUES (%s, %s, %s);"
            cur.executemany(insert_suite, [(new_run_id, s['name'], s['result']) for s in suite_array])

        update_items = "UPDATE harvest.items SET last_validation = %s, validation_passed = %s WHERE identifier = %s"
        cur.execute(update_items, (now, passed, identifier))

        conn.commit()
        return f"Completed: {identifier} (Run ID: {new_run_id})"

    except Exception as e:
        conn.rollback()
        return f"Failed: {identifier} - Error: {e}"
    finally:
        cur.close()
        conn.close()

def check_validator_health():
    """Checks if the ETF Validator is reachable before starting."""
    print(f"Checking connection to ETF Validator at {ETF_URL}...")
    try:
        # We try to hit the version or status endpoint with a short timeout
        response = requests.get(f"{ETF_URL}/v2/status.json", timeout=5)
        if response.status_code == 200:
            print("[OK] Validator is online.")
            return True
        else:
            print("Validator is running, but status check does not work. Status code is " + str(response.status_code))
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Cannot reach the Validator at {ETF_URL}.")
        print(">>> Please start your ETF Validator (Docker or JAR) and try again.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error checking validator: {e}")
        return False

def main():
    if not check_validator_health():
        return

    auto_cleanup_stuck_records()

    service_suite_ids = get_suite_ids(SERVICE_MD)
    dataset_suite_ids = get_suite_ids(DATASET_MD)

    # Fetch all records initially
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    query = """
        SELECT identifier, resultobject, itemtype
        FROM harvest.items
        WHERE source = 'INSPIRE' AND insert_date > COALESCE(last_validation, '1900-01-01'::timestamp)
     """
    cur.execute(query)
    records = cur.fetchall()
    cur.close()
    conn.close()

    print(f"Total records to process: {len(records)}. Using {MAX_WORKERS} workers.")

    # Use ThreadPoolExecutor to run validations in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = [executor.submit(process_single_record, rec, service_suite_ids, dataset_suite_ids) for rec in records]

        # Monitor results as they complete
        for future in futures:
            print(future.result())


if __name__ == "__main__":
    main()
