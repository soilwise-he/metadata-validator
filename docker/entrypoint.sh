#!/bin/sh
set -e

if [ "${SKIP_SCHEMA_BOOTSTRAP:-0}" != "1" ]; then
  python /app/bootstrap_schema.py
fi

MODE="${RUN_MODE:-sequential}"

case "$MODE" in
  sequential)
    exec python /app/validationByTestSuites.py "$@"
    ;;
  concurrent)
    exec python /app/concurrentValidation.py "$@"
    ;;
  *)
    echo "Error: unknown RUN_MODE '${MODE}'. Use 'sequential' or 'concurrent'."
    exit 1
    ;;
esac
