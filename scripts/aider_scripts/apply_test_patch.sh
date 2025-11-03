#!/bin/bash

HONOURS_DIR="$1"
TEST_PATCH_PATH="$2"

DUCKDB_DIR="$HONOURS_DIR/repos/duckdb"

cd "$DUCKDB_DIR" || exit 1

git apply "$TEST_PATCH_PATH"