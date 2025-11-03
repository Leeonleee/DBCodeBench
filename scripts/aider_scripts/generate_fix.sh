# This script generates one completion

#!/bin/bash

set -e

# Usage: ./generate_fix.sh <honours_dir> <problem_directory> <problem_id> <model_name> [--thinking-tokens <value>] [--reasoning-effort <value>]
# Run from project root directory

# Arguments
HONOURS_DIR="$1"
PROBLEM_DIR="$2"
PROBLEM_ID="$3"
MODEL_NAME="$4"

# Optional parameters
THINKING_TOKENS=""
REASONING_EFFORT=""

# Parse optional arguments
shift 4
while [[ $# -gt 0 ]]; do
  case $1 in
    --thinking-tokens)
      THINKING_TOKENS="$2"
      shift 2
      ;;
    --reasoning-effort)
      REASONING_EFFORT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Paths
DUCKDB_DIR="$HONOURS_DIR/repos/duckdb"
IGNORE_SRC="$HONOURS_DIR/scripts/aider_scripts/.aiderignore"
PROMPT_PATH="$PROBLEM_DIR/$PROBLEM_ID.prompt"
JSON_PATH="$PROBLEM_DIR/$PROBLEM_ID.json"


# Extract modified files
MODIFIED_FILES=$(jq -r '.modified_files[]' "$JSON_PATH")

# Load .env from honours directory
if [ -f "$HONOURS_DIR/.env" ]; then
  set -a
  source "$HONOURS_DIR/.env"
  set +a
  echo "Loaded environment variables from .env"
else
  echo ".env file not found in $HONOURS_DIR"
  exit 1
fi

# Copy .aiderignore into DuckDB
cp "$IGNORE_SRC" "$DUCKDB_DIR/.aiderignore"
echo "Copied .aiderignore into duckdb"

# Run aider from within duckdb

# --show-prompts to show the prompt being sent to the models (doesn't include the content in the .prompt file)
# --map-tokens 0 to disable the repo
cd "$DUCKDB_DIR" || exit 1

# Build aider command with optional parameters
AIDER_CMD="aider --model \"$MODEL_NAME\" --no-gitignore --yes --disable-playwright"

# Add thinking tokens parameter (default to 0 if not specified)
if [ -n "$THINKING_TOKENS" ]; then
  AIDER_CMD="$AIDER_CMD --thinking-tokens $THINKING_TOKENS"
else
  AIDER_CMD="$AIDER_CMD --thinking-tokens 0"
fi

# Add reasoning effort parameter
if [ -n "$REASONING_EFFORT" ]; then
  AIDER_CMD="$AIDER_CMD --reasoning-effort $REASONING_EFFORT"
fi

# Add the prompt file and modified files
AIDER_CMD="$AIDER_CMD -f \"$PROMPT_PATH\" $MODIFIED_FILES"

# Execute the command
eval $AIDER_CMD


# Track success
if [ $? -eq 0 ]; then
  echo "Fix generation succeeded"
  exit 0
else
  echo "Fix generation failed"
  exit 1
fi
