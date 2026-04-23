import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQL_PATH = os.environ.get("SCHEMA_SQL_PATH", "/app/create_new_tables.sql")


def main():
    required = {
        "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
        "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
        "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
        "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"Error: required environment variables not set: {', '.join(missing)}")
        sys.exit(1)

    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    print(f"Applying schema from {SQL_PATH}...")
    conn = psycopg2.connect(
        dbname=required["POSTGRES_DB"],
        user=required["POSTGRES_USER"],
        password=required["POSTGRES_PASSWORD"],
        host=required["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Schema is up to date.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
