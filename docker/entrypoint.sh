#!/bin/sh
set -e

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
