#!/bin/bash

HONOURS_DIR="$1"
COMMIT="$2"

DUCKDB_DIR="$HONOURS_DIR/repos/duckdb"

cd "$DUCKDB_DIR" || exit 1

git stash
git checkout "$COMMIT"
