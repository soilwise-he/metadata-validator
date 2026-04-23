#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.test.yml"

cleanup() {
  $COMPOSE down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL [$desc]: expected '$expected', got '$actual'"
    exit 1
  fi
  echo "OK   [$desc]"
}

psql_count() {
  $COMPOSE exec -T postgres psql -U soilwise -d soilwise -At -c "$1"
}

# ---------------------------------------------------------------------------
echo "==> Building image..."
$COMPOSE build bootstrap-test

# ---------------------------------------------------------------------------
echo ""
echo "==> Test 1: missing env vars produce a non-zero exit and a clear error"
set +e
OUTPUT=$(
  $COMPOSE run --rm --no-deps \
    -e POSTGRES_HOST= -e POSTGRES_DB= -e POSTGRES_USER= -e POSTGRES_PASSWORD= \
    bootstrap-test 2>&1
)
EXIT_CODE=$?
set -e
assert_eq "exit code on missing env vars" "1" "$EXIT_CODE"
echo "$OUTPUT" | grep -q "required environment variables" || {
  echo "FAIL [missing-env-vars message]: unexpected output:"
  echo "$OUTPUT"
  exit 1
}
echo "OK   [missing-env-vars message]"

# ---------------------------------------------------------------------------
echo ""
echo "==> Test 2: bootstrap creates tables and columns against a real Postgres"
$COMPOSE up -d postgres
$COMPOSE run --rm bootstrap-test

TABLES=$(psql_count "
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = 'harvest'
  AND table_name IN ('validation_runs', 'validation_suite_results');
")
assert_eq "validation tables created"     "2" "$TABLES"

COLUMNS=$(psql_count "
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'harvest' AND table_name = 'items'
  AND column_name IN ('last_validation', 'validation_passed');
")
assert_eq "columns added to harvest.items" "2" "$COLUMNS"

# ---------------------------------------------------------------------------
echo ""
echo "==> Test 3: re-running bootstrap is idempotent (IF NOT EXISTS guards)"
$COMPOSE run --rm bootstrap-test

TABLES_AFTER=$(psql_count "
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = 'harvest'
  AND table_name IN ('validation_runs', 'validation_suite_results');
")
assert_eq "tables still present after second run" "2" "$TABLES_AFTER"

# ---------------------------------------------------------------------------
echo ""
echo "All tests passed."
