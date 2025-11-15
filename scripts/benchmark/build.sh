
#!/bin/bash

HONOURS_DIR="$1"
DUCKDB_DIR="$HONOURS_DIR/repos/duckdb"

cd "$DUCKDB_DIR" || exit 1

echo "Starting build..."
make -j$(nproc) # can change to any number, to use all -j$(nproc)

if [ $? -eq 0 ]; then
  echo "Build succeeded"
  exit 0
else
  echo "Build failed"
  exit 1
fi