#!/bin/bash
set -e

# Usage: ./run_tests <honours_dir> <test_file_1> <test_file_2> ...

HONOURS_DIR="$1"
shift
TEST_FILES=("$@")

DUCKDB_DIR="$HONOURS_DIR/repos/duckdb"
UNITTEST_BINARY="$DUCKDB_DIR/build/release/test/unittest"

ALL_PASSED=true

cd "$DUCKDB_DIR" || exit 1

for test_file in "${TEST_FILES[@]}"; do
  echo "Running test: $test_file"
  "$UNITTEST_BINARY" "$test_file"

  if [ $? -ne 0 ]; then
    echo "Test failed: $test_file"
    ALL_PASSED=false
  else
    echo "Test passed: $test_file"
  fi
done

if [ "$ALL_PASSED" = true ]; then
  exit 0
else
  exit 1
fi