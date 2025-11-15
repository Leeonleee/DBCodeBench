# DBCodeBench

DBCodeBench is a reproducible benchmark for evaluating large language models (LLMs) on real-world C++ DBMS bug-fixing tasks. It provides a verified dataset and an automated pipeline for generating, applying, compiling, and testing LLM-produced patches against DuckDB.

This benchmark is intended for researchers and engineers studying how well LLMs can fix bugs in large, real-world C++ systems code — going beyond small function-level problems and into realistic system-level patches.

## Highlights

- 81 verified, real-world C++ bug-fixing tasks extracted from DuckDB.
- Automated pipeline: patch generation, patch application, compilation (GCC/CMake), and test execution.
- Reproducible Docker environment for consistent compilation and testing.
- Difficulty proxies per task (lines changed, files modified, tests modified) and analysis scripts for pass@k, build success, and difficulty correlations.


## Installation & Setup

The following steps walks through setting up DBCodeBench in a Docker container. We use the `gcc:11` Docker image to ensure consistent compilation and testing across different machines.

### Prerequisites

- Docker installed on your host machine
- Git configured with SSH access to GitHub
- At least 20GB of free disk space

#### 1. Docker Environment

Pull and start the GCC 11 Docker container:

```bash
# Pull the official GCC 11 image
docker pull gcc:11

# Create and start the container
docker run -it --name duckdb-bench gcc:11 bash

# For subsequent sessions, use:
docker start duckdb-bench
docker exec -it duckdb-bench bash
```

#### 2. SSH setup

Generate SSH keys for cloning repositories

```bash
mkdir -p ~/.ssh
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""

# Display your public key to add to GitHub
cat ~/.ssh/id_rsa.pub
```

Copy the output and add it to your GitHub account.

#### 3. Clone Repositories

```bash
# Clone the benchmark repository
cd ~
git clone git@github.com:Leeonleee/DBCodeBench.git

# Clone DuckDB into the repos directory
cd DBCodeBench/repos/
git clone https://github.com/duckdb/duckdb.git
```

#### 4. Install System Dependencies

```bash
# Update package lists
apt-get update

# Install build tools for DuckDB
apt install -y cmake ccache

# Install utilities for benchmark scripts
apt install -y jq
```

#### 5. Python Environment

We use `uv` for Python dependency management:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Navigate to benchmark directory
cd ~/honours

# Initialize Python 3.11 (required for aider-chat)
uv python install 3.11
uv python pin 3.11

# Install dependencies (automatically reads pyproject.toml)
uv sync
```

#### 6. Configure Aider

Ignore this step if you are not using Aider.

Create an `.aiderignore` file to exclude unnecessary directories

```bash
echo "extension/**" > scripts/aider_scripts/.aiderignore
```

#### 7. Environment Variables

Create a `.env` file in the repository root with your API keys

```bash
OPENROUTER_API_KEY=your_key_here
```

#### 8. Configure ccache

Set ccache to use more storage

```bash
ccache --max-size 20G
```

#### Make Scripts Executable

```bash
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

## Running the benchmark

To start the benchmark, the following command-line arguments are required:

- `--m`: the name of the model you want to test, e.g. `openai/gpt5`
- `--k`: the number of generations you want each task to have
- `--thinking-tokens`: optional, specifies a thinking token budget for models that support it
- `--reasoning-effort`: optional, specifies a reasoning effort for models that support it

Example command (using uv):

```bash
uv run scripts/benchmark/benchmark.py \
--m openrouter/anthropic/claude-sonnet-4 \
--thinking-tokens 24k \
--k 5
```

## Analysis

The `scripts/analysis/` directory contains scripts to compute standard metrics:

- pass@k and patch success rate
- build success / compile failure rate
- difficulty correlations (lines changed, files changed, tests modified)


There are R scripts and notebooks for plotting and thesis figures in `visualisations`


## Contributing

Contributions are welcome. Suggested contribution flow:

1. Fork the repo and add new tasks under `datasets/`.
2. Add generation/test scripts under `benchmarks/` if needed.
3. Add analysis scripts under `analysis/` as needed.
4. Submit a PR documenting your additions and referencing sample runs.

Please include:
- task metadata (commit, test names)
- clear licensing for any added assets

## Contact & Citation

If you use DBCodeBench in research, please cite it and contact the maintainer:

- Leon Lee — contact@leonlee.io
