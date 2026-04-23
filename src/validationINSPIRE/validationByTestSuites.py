import psycopg2
import requests
import time
import json
import zipfile
import io
import os
import sys
from datetime import datetime
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
MAX_WORKERS = 5  # Number of concurrent validations to run at once

# Target Labels for dynamic ID lookup
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
        data = response.json()
        current_status = data.get("EtfItemCollection", {}).get("testRuns", {}).get("TestRun", {}).get("status")

        if current_status in ["RUNNING", "UNDEFINED", "STARTING"]:
            continue

        # Terminal state reached
        passed = (current_status == "PASSED")
        # Always analyze results to get the detailed suite array
        suites_results = analyze_results(data)

        return passed, data, suites_results

def main():
    # 1. Fetch the Suite IDs once at the start
    service_suite_ids = get_suite_ids(SERVICE_MD)
    dataset_suite_ids = get_suite_ids(DATASET_MD)

    if not service_suite_ids and not dataset_suite_ids:
        print("Error: Could not fetch suite IDs from ETF. Check connection/labels.")
        return

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Query the items to validate
        query = "SELECT identifier, resultobject, itemtype FROM harvest.items"
        cur.execute(query)
        records = cur.fetchall()
        print(f"Total records found: {len(records)}")

        for identifier, xml_data, item_type in records:
            print(f"\n--- Processing: {identifier} ---")
            try:
                # 1. Register the Object in ETF
                obj_id = create_test_object(identifier, xml_data)
                print(f"Object Registered: {obj_id}")

                # 2. Determine which suites to run based on item type
                suite_ids = service_suite_ids if item_type == "service" else dataset_suite_ids

                if not suite_ids:
                    print(f"Skipping {identifier}: No suites found for type '{item_type}'")
                    continue

                # 3. Trigger Validation and wait for results
                passed, full_report, suite_array = run_validation(obj_id, suite_ids)
                print(f"Run Finished. Overall Pass: {passed}")

                # 4. Insert Main Run Record into validation_runs
                # We use RETURNING run_id to link the suite details
                insert_run_query = """
                    INSERT INTO harvest.validation_runs
                    (metadata_identifier, status_passed, validation_timestamp, full_report_json)
                    VALUES (%s, %s, %s, %s) RETURNING run_id;
                """
                cur.execute(insert_run_query, (
                    identifier,
                    passed,
                    datetime.now(),
                    json.dumps(full_report)
                ))
                new_run_id = cur.fetchone()[0]

                # 5. Insert individual Suite Results into validation_suite_results
                if suite_array:
                    insert_suite_query = """
                        INSERT INTO harvest.validation_suite_results (run_id, suite_name, result_status)
                        VALUES (%s, %s, %s);
                    """
                    # Prepare list of tuples for batch insertion
                    suite_data_to_insert = [
                        (new_run_id, s['name'], s['result']) for s in suite_array
                    ]
                    cur.executemany(insert_suite_query, suite_data_to_insert)

                    for s in suite_array:
                        print(f"  > Suite: {s['name']} -> {s['result']}")

                # 6. Optional: Update the timestamp on the main items table
                # (Comment this block out if you don't have UPDATE permissions on harvest.items)
                # TODO: this shall be updated (i dont have permission to do that)
                try:
                    update_items_query = "UPDATE harvest.items SET last_validation = %s WHERE identifier = %s"
                    cur.execute(update_items_query, (datetime.now(), identifier))
                except Exception as e:
                    print(f"Note: Could not update last_validation on items table: {e}")
                    conn.rollback()  # Recover from the error to continue the loop

                # Commit the changes for this specific record
                conn.commit()
                print(f"Successfully saved results to database for run ID: {new_run_id}")

            except Exception as e:
                print(f"Failed processing {identifier}: {e}")
                conn.rollback()

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    main()
