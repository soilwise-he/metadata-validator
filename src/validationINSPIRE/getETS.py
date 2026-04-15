import requests
import json

# Configuration
ETF_BASE_URL = "http://localhost:8090/validator"
ETS_ENDPOINT = f"{ETF_BASE_URL}/v2/ExecutableTestSuites.json"


def get_suites():
    print(f"Connecting to {ETS_ENDPOINT}...\n")
    try:
        response = requests.get(ETS_ENDPOINT, timeout=10)
        response.raise_for_status()

        data = response.json()

        # ETF API structure: EtfItemCollection -> executableTestSuites -> ExecutableTestSuite (list)
        suites = data.get('EtfItemCollection', {}).get('executableTestSuites', {}).get('ExecutableTestSuite', [])

        if not suites:
            print("No Test Suites found.")
            return

        # Print header
        print(f"{'ID':<40} | {'LABEL'}")
        print("-" * 100)

        for suite in suites:
            suite_id = suite.get('id', 'N/A')
            label = suite.get('label', 'No Label')
            print(f"{suite_id:<40} | {label}")

    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to ETF. Is Docker running on port 8090?")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    get_suites()