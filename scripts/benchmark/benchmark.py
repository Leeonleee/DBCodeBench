"""
Usage: python aider_benchmark.py --m <model_name> --k <num_completions> [--thinking-tokens <value>] [--reasoning-effort <value>]

Optional parameters:
  --thinking-tokens: Thinking tokens value (e.g., 0, 8k, 16k, 24k)
  --reasoning-effort: Reasoning effort level (low, medium, high)

Examples:
  python aider_benchmark.py --m openrouter/openai/gpt-5 --k 5 --reasoning-effort low
  python aider_benchmark.py --m openrouter/google/gemini-2.5-pro --k 5 --thinking-tokens 8k
  python aider_benchmark.py --m openrouter/anthropic/claude-sonnet-4 --k 5 --thinking-tokens 0
"""

import argparse, shutil
from pathlib import Path
import subprocess
from datetime import datetime
import json
import csv
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv
import time

debug = False

# Constants
HONOURS_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BENCHMARK_DIR = (SCRIPT_DIR.parent.parent / "benchmarks/duckdb_benchmark").resolve()
DEFAULT_OUTPUT_DIR = (SCRIPT_DIR.parent.parent / "archive").resolve()

load_dotenv(dotenv_path=HONOURS_DIR / ".env")

if debug:
    DEFAULT_BENCHMARK_DIR = (SCRIPT_DIR.parent.parent / "benchmarks/testbenchmark").resolve()


def send_email_notification(subject, body, sender_email, app_password, recipient_email):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run benchmark pipeline")
    parser.add_argument("--m", required=True, help="Model to use")
    parser.add_argument("--k", type=int, required=True, help="Number of completions per problem")
    parser.add_argument("--dir", type=str, default=DEFAULT_BENCHMARK_DIR, help="Path to benchmark directory")
    parser.add_argument("--out", type=str, default=DEFAULT_OUTPUT_DIR, help="Where to move organized results")
    parser.add_argument("--thinking-tokens", type=str, help="Thinking tokens value (e.g., 0, 8k, 16k, 24k)")
    parser.add_argument("--reasoning-effort", type=str, choices=['low', 'medium', 'high'], help="Reasoning effort level")
    return parser.parse_args()


def run(cmd, cwd=None, env=None, check=True, log_file=None, timeout=None):
    if isinstance(cmd, str):
        shell = True
        printable_cmd = cmd
    else:
        shell = False
        printable_cmd = " ".join(cmd)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"[{timestamp}] Running command: {printable_cmd}\n"

    if log_file:
        with open(log_file, 'a') as f:
            f.write(header)

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        shell=shell,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True
    )

    stdout_lines = []
    stderr_lines = []

    with open(log_file, 'a') if log_file else open(os.devnull, 'w') as log:
        from threading import Thread
        def read_stream(stream, buffer, prefix):
            for line in stream:
                log.write(f"{prefix}: {line}")
                log.flush()
                buffer.append(line)

        threads = []
        threads.append(Thread(target=read_stream, args=(process.stdout, stdout_lines, "STDOUT")))
        threads.append(Thread(target=read_stream, args=(process.stderr, stderr_lines, "STDERR")))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    return_code = process.wait()

    if check and return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd, output=''.join(stdout_lines), stderr=''.join(stderr_lines))

    class Result:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    return Result(return_code, ''.join(stdout_lines), ''.join(stderr_lines))


def main():
    args = parse_arguments()
    start_time = time.time()
    print(f"Model: {args.m}, Completions: {args.k}, Benchmark Directory: {args.dir}, Output Directory: {args.out}")

    # Logging setup
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    safe_model_name = args.m.replace("/", "_").replace(":", "_")
    
    # Build run name with optional thinking tokens and reasoning effort
    name_parts = [timestamp, safe_model_name]
    
    if args.thinking_tokens:
        name_parts.append(f"thinking{args.thinking_tokens}")
    
    if args.reasoning_effort:
        name_parts.append(f"reasoning{args.reasoning_effort}")
    
    name_parts.append(f"k{args.k}")
    run_name = "_".join(name_parts)

    output_dir = Path("outputs") / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / f"{run_name}.log"
    summary_csv_path = output_dir / f"{run_name}_summary.csv"
    attempts_csv_path = output_dir / f"{run_name}_attempts.csv"

    # Write a small run meta file for provenance
    meta_path = output_dir / f"{run_name}_meta.json"
    meta = {
        "run_id": run_name,
        "model": args.m,
        "Kmax": args.k,
        "benchmark_dir": str(Path(args.dir).resolve()),
        "repo_root": str(HONOURS_DIR),
        "timestamp": timestamp,
    }
    
    # Add optional parameters to metadata
    if args.thinking_tokens:
        meta["thinking_tokens"] = args.thinking_tokens
    if args.reasoning_effort:
        meta["reasoning_effort"] = args.reasoning_effort
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # Prepare CSV writers
    attempts_headers = ["problem", "attempt_index", "generation_success", "build_success", "test_success"]
    summary_headers = ["problem", "total_generations", "successful_builds", "failed_builds", "passed_tests", "failed_tests"]

    # Keep per-problem summary in memory
    results = {}

    try:
        # Open attempts CSV once and append rows as we go
        with open(attempts_csv_path, 'w', newline='') as attempts_csv:
            attempts_writer = csv.DictWriter(attempts_csv, fieldnames=attempts_headers)
            attempts_writer.writeheader()

            problems = sorted(
                [p for p in Path(args.dir).iterdir() if p.is_dir()],
                key=lambda p: int(p.name)
            )
            for problem in problems:
                print(f"Processing problem: {problem.name}")

                results[problem.name] = {
                    "problem": problem.name,
                    "total_generations": 0,
                    "successful_builds": 0,
                    "failed_builds": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                }

                # Parse json file to get problem details
                problem_json = problem / f"{problem.name}.json"
                if not problem_json.exists():
                    print(f"Problem JSON file not found for {problem.name}, skipping.")
                    continue

                with open(problem_json, 'r') as f:
                    problem_data = json.load(f)

                base_commit = problem_data.get("base_commit")
                modified_test_files = problem_data.get("modified_test_files", [])

                for i in range(args.k):
                    attempt_idx = i + 1
                    print(f"Generating completion {attempt_idx} for {problem.name} using model {args.m}")

                    # reset repo
                    run(["bash", "scripts/aider_scripts/clean_repo.sh", str(HONOURS_DIR)], log_file=log_path)
                    # checkout base commit
                    run(["bash", "scripts/aider_scripts/checkout.sh", str(HONOURS_DIR), base_commit], log_file=log_path)
                    # apply test patch
                    test_patch_path = problem / "test.patch"
                    run(["bash", "scripts/aider_scripts/apply_test_patch.sh", str(HONOURS_DIR), str(test_patch_path)], log_file=log_path)

                    # generate fix (one-shot)
                    generate_cmd = ["bash", "scripts/aider_scripts/generate_fix.sh", str(HONOURS_DIR), str(problem), str(problem.name), str(args.m)]
                    
                    # Add optional parameters
                    if args.thinking_tokens:
                        generate_cmd.extend(["--thinking-tokens", args.thinking_tokens])
                    if args.reasoning_effort:
                        generate_cmd.extend(["--reasoning-effort", args.reasoning_effort])
                    
                    gen = run(
                        generate_cmd,
                        log_file=log_path,
                        check=False
                    )
                    generation_success = int(gen.returncode == 0)
                    results[problem.name]["total_generations"] += 1

                    # Default per-attempt outcomes
                    build_success = 0
                    test_success = 0

                    if not generation_success:
                        print(f"❌ Completion generation failed for {problem.name} attempt {attempt_idx}, skipping build/tests.")
                        # record attempt row
                        attempts_writer.writerow({
                            "problem": problem.name,
                            "attempt_index": attempt_idx,
                            "generation_success": generation_success,
                            "build_success": build_success,
                            "test_success": test_success,
                        })
                        attempts_csv.flush()
                        continue

                    print(f"✅ Completion generated for {problem.name} attempt {attempt_idx}")

                    # build
                    bld = run(["bash", "scripts/aider_scripts/build.sh", str(HONOURS_DIR)], log_file=log_path, check=False)
                    if bld.returncode != 0:
                        print(f"❌ Build failed for {problem.name} attempt {attempt_idx}, skipping tests.")
                        results[problem.name]["failed_builds"] += 1
                        # record attempt row
                        attempts_writer.writerow({
                            "problem": problem.name,
                            "attempt_index": attempt_idx,
                            "generation_success": generation_success,
                            "build_success": build_success,
                            "test_success": test_success,
                        })
                        attempts_csv.flush()
                        continue

                    print(f"✅ Build successful for {problem.name} attempt {attempt_idx}")
                    results[problem.name]["successful_builds"] += 1
                    build_success = 1

                    # test
                    tst = run(["bash", "scripts/aider_scripts/run_tests.sh", str(HONOURS_DIR)] + modified_test_files, log_file=log_path, check=False)
                    if tst.returncode == 0:
                        print(f"✅ Tests passed for {problem.name} attempt {attempt_idx}")
                        results[problem.name]["passed_tests"] += 1
                        test_success = 1
                    else:
                        print(f"❌ Tests failed for {problem.name} attempt {attempt_idx}")
                        results[problem.name]["failed_tests"] += 1
                        test_success = 0

                    # record attempt row
                    attempts_writer.writerow({
                        "problem": problem.name,
                        "attempt_index": attempt_idx,
                        "generation_success": generation_success,
                        "build_success": build_success,
                        "test_success": test_success,
                    })
                    attempts_csv.flush()

        # write summary CSV
        with open(summary_csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=summary_headers)
            writer.writeheader()
            for row in results.values():
                writer.writerow(row)

        print(f"Results and logs saved to {output_dir}")

        # Send email notification
        elapsed_seconds = int(time.time() - start_time)
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed_str = f"{hours}h {minutes}m {seconds}s"

        body = (
            f"Model: {args.m}\n"
            f"Run ID: {run_name}\n"
            f"Results saved to:\n"
            f"  Attempts: {attempts_csv_path.resolve()}\n"
            f"  Summary : {summary_csv_path.resolve()}\n"
            f"Total runtime: {elapsed_str}\n"
        )

        send_email_notification(
            subject="✅ Benchmark Completed!",
            body=body,
            sender_email=os.getenv("EMAIL_USER"),
            app_password=os.getenv("EMAIL_PASS"),
            recipient_email=os.getenv("EMAIL_USER")
        )

    except KeyboardInterrupt:
        print("Emergency stop requested. Writing results to CSV and exiting")
        # Partial summary dump
        partial_summary = summary_csv_path.with_name(f"{summary_csv_path.stem}_partial.csv")
        with open(partial_summary, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=summary_headers)
            writer.writeheader()
            for row in results.values():
                writer.writerow(row)
        print(f"Partial summary saved to {partial_summary}")

        # attempt CSV already has rows flushed incrementally
        # Cleanup
        try:
            run(["bash", "scripts/aider_scripts/clean_repo.sh", str(HONOURS_DIR)], log_file=log_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()