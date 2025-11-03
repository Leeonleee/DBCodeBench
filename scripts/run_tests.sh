#!/bin/bash

TESTS=(
  "test/sql/types/nested/map/map_from_entries/data_types.test"
)

PASS=0
FAIL=0

for test in "${TESTS[@]}"; do
  echo "Running: $test"
  OUTPUT=$("../duckdb/build/release/test/unittest" "$test")
  echo "$OUTPUT"

  if echo "$OUTPUT" | grep -q "All tests passed"; then
    ((PASS++))
  else
    ((FAIL++))
  fi
done

echo "======================================"
echo "Total tests: $((PASS + FAIL))"
echo "Passed: $PASS"
echo "Failed: $FAIL"
