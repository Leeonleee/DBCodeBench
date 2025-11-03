import os
import subprocess
import json
import sys
from datetime import datetime

# Configurations
PR_FOLDER_PATH = "../dragonflydb_unverified"
# PR_FOLDER_PATH = "../prs"
DUCKDB_REPO_PATH = "../repos/dragonfly"
PROCESS_SCRIPT_PATH = "process_single_pr.py"

# def run(cmd, cwd=None, check=True):
#     result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
#     if check and result.returncode != 0:
#         print(f"[Error] Command failed: {cmd}")
#         print(result.stdout)
#         print(result.stderr)
#         return None
#     return result

# run with full terminal output
def run(cmd, cwd=None, check=True, log_file=None):
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    stdout, stderr = [], []

    for line in process.stdout:
        print(line, end='')
        stdout.append(line)
        if log_file:
            log_file.write(line)
    for line in process.stderr:
        print(line, end='', file=sys.stderr)
        stderr.append(line)
        if log_file:
            log_file.write(line)

    process.wait()

    if check and process.returncode != 0:
        print(f"[Error] Command failed: {cmd}")
        if log_file:
            log_file.write(f"[Error] Command failed: {cmd}\n")
        return None

    class Result:
        def __init__(self, stdout, stderr, returncode):
            self.stdout = ''.join(stdout)
            self.stderr = ''.join(stderr)
            self.returncode = returncode

    return Result(stdout, stderr, process.returncode)



def apply_patch(patch_path, repo_path, log_file):
    return run(f"git apply {patch_path}", cwd=repo_path, log_file=log_file)

def build_duckdb(repo_path, log_file):
    return run("make -j$(nproc)", cwd=repo_path, log_file=log_file)

def run_test(test_paths, repo_path, log_file):
    unittest_path = "build/release/test/unittest"
    for test_path in test_paths:
        result = run(f"{unittest_path} {test_path}", cwd=repo_path, check=False, log_file=log_file)
        if result is None or "All tests passed" not in result.stdout:
            return False
    return True


def get_test_paths_from_patch(patch_path):
    test_paths = []
    with open(patch_path) as f:
        for line in f:
            if line.startswith("+++ b/"):
                file_path = line[len("+++ b/"):].strip()
                # Heuristic: include anything with 'test' in the filename or directory
                if "test" in os.path.basename(file_path).lower() or "/test" in file_path.lower():
                    test_paths.append(file_path)
    return test_paths


def log_invalid_pr(pr, valid_prs, log_file):
    log_file.write(f"\n❌ PR {pr} is not valid\n")
    log_file.write("✅ Valid PRs so far:\n")
    for verified_pr in valid_prs:
        print(verified_pr)
        log_file.write(verified_pr + "\n")
    log_file.flush()


def main():
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_path = f"run_log_{timestamp}.txt"

    with open(log_path, "w") as log_file:
        valid_prs = []
        max_prs_to_test = 1000
        tested_pr_count = 0

        for pr in sorted(os.listdir(PR_FOLDER_PATH), key=lambda x: int(x) if x.isdigit() else float('inf')):
            if tested_pr_count >= max_prs_to_test:
                break
            pr_path = os.path.join(PR_FOLDER_PATH, pr)
            if not os.path.isdir(pr_path):
                continue

            print(f"\n--- Testing PR {pr} ---")

            # Reset DuckDB repo
            run("git reset --hard", cwd=DUCKDB_REPO_PATH, log_file=log_file)
            run("git clean -fd", cwd=DUCKDB_REPO_PATH, log_file=log_file)

            # Process PR
            process = run(f"python3 {PROCESS_SCRIPT_PATH} {pr_path} {DUCKDB_REPO_PATH}", log_file=log_file)
            if process is None:
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)
                continue
            # Checkout to PR commit
            with open(os.path.join(pr_path, f"{pr}.json")) as f:
                commit_hash = json.load(f)["base_commit"]
            if not run(f"git checkout {commit_hash}", cwd=DUCKDB_REPO_PATH, log_file=log_file):
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue

            # COMMENT START HERE IF YOU WANT TO ONLY PROCESS, NOT VERIFY
            """

            # Compile baseline code
            print("🔧 Compiling code...")
            if not build_duckdb(DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Compilation failed")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ Compilation succeeded (Expected behaviour)")
            # Get test path
            test_patch_path = os.path.join(pr_path, "test.patch")
            test_rel_path = get_test_paths_from_patch(test_patch_path)
            if not test_rel_path:
                print(f"Could not determine test path for PR {pr}")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue

            # Run baseline test (should pass)
            print("✅ Running baseline test... (should pass)")
            if not run_test(test_rel_path, DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Baseline test failed")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ Baseline test passed (Expected behaviour)")

            # Apply test.patch and rerun test (should fail)
            print("📄 Applying test.patch...")
            if not apply_patch(test_patch_path, DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Failed to apply test.patch")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ test.patch applied (Expected behaviour)")
            print("🔧 Compiling code...")
            if build_duckdb(DUCKDB_REPO_PATH, log_file=log_file) is None:
                print("❌ Compilation failed")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ Compilation succeeded (Expected behaviour)")
            print("🧪 Running modified test (should fail)...")
            if run_test(test_rel_path, DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Test did not fail after applying test.patch")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ Modified test failed (Expected behaviour)")

            # Apply fix.patch and rerun test (should pass)
            print("📄 Applying fix.patch...")
            if not apply_patch(os.path.join(pr_path, "fix.patch"), DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Failed to apply fix.patch")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ fix.patch applied (Expected behaviour)")
            print("🔧 Compiling code...")
            if build_duckdb(DUCKDB_REPO_PATH, log_file=log_file) is None:
                print("❌ Compilation failed")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue
            print("✅ Compilation succeeded (Expected behaviour)")
            print("🧪 Running fixed test (should pass)...")
            if not run_test(test_rel_path, DUCKDB_REPO_PATH, log_file=log_file):
                print("❌ Final test failed")
                # Print and log out valid PRs so far
                log_invalid_pr(pr, valid_prs, log_file)

                continue

            print(f"✅ PR {pr} is valid")
            valid_prs.append(pr)
            tested_pr_count += 1

            # print out valid prs
            # Print and log out valid PRs so far
            log_file.write("\n✅ Valid PRs so far:\n")
            for verified_pr in valid_prs:
                print(verified_pr)
                log_file.write(verified_pr + "\n")
            log_file.flush()  # optional: flush to disk immediatelyA

            # COMMENT END HERE IF YOU WANT TO PROCESS ONLY
            """
            # Reset DuckDB repo
            run("git reset --hard", cwd=DUCKDB_REPO_PATH, log_file=log_file)
            run("git clean -fd", cwd=DUCKDB_REPO_PATH, log_file=log_file)

        print("\n=== Valid PRs ===")
        for pr in valid_prs:
            print(pr)

if __name__ == "__main__":
    main()
