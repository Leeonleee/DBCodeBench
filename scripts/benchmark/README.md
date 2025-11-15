# Aider Script Readme

This readme contains all the information about the Aider version of the benchmark script

# Script Methodology

1. Generate all

# Scripts

# How to use

## Run single test

```bash
aider --no-gitignore --yes --model <model_name> -f <prompt_file_path> <file1> <file2> <file...>
```

Example

```bash
aider --model o3 --no-gitignore --yes -f ../aider_test/4713/4713.prompt src/function/table/read_csv.cpp
```

## Automatically run a single test

- Use the `apply_once.sh` script
  - e.g. `apply_once.sh <problem_id> <model_name>`
  - This script will apply environment variables, copy `.aiderignore` and then run the above command
- Afterwards you can `make`, apply tests and run the tests

# Planned Script Workflow

- Run overall script
  - Start from first problem
  - Checkout to correct commit
  - Apply test.patch
  - Run `apply_once.sh` to generate fix
  - `make`
  - Run test to check if it passes
  - Log result
  - Repeat `k` times
  


# Notes




