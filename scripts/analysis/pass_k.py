"""
Usage: python3 pass_k.py --dir <directory> --k <k_value> [--detailed] [--metric <metric>]
"""
import csv
import math
import sys
import os
import json
import argparse
from pathlib import Path
from collections import defaultdict

def comb(n, k):
    if k > n:
        return 0
    return math.comb(n, k)

def pass_at_k(n, c, k):
    if c == 0 or k > n:
        return 0.0
    return 1.0 - comb(n - c, k) / comb(n, k)

def extract_model_name(folder_name, metadata=None):
    """Extract a clean model name from the folder name."""
    # Remove timestamp and k value
    parts = folder_name.split('_')
    if len(parts) >= 3:
        # Skip timestamp parts and k part, join the middle
        model_parts = []
        skip_first = True  # Skip timestamp
        for part in parts:
            if skip_first:
                skip_first = False
                continue
            if part.startswith('k') and part[1:].isdigit():
                break  # Stop at k5, k10, etc.
            model_parts.append(part)
        
        if model_parts:
            model_name = '_'.join(model_parts)
            # Clean up common prefixes
            if model_name.startswith('openrouter_'):
                model_name = model_name.replace('openrouter_', '')
            return model_name
    
    return folder_name

def compute_pass_at_k_from_attempts(attempts_file, k, metric='test_success', detailed=False):
    """Compute pass@k from attempts CSV file."""
    if not os.path.exists(attempts_file):
        if detailed:
            print(f"Attempts file not found: {attempts_file}")
        return None, []
    
    # Group attempts by problem
    problem_attempts = defaultdict(list)
    
    try:
        with open(attempts_file, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                problem_id = row['problem']
                attempt_index = int(row['attempt_index'])
                success = int(row[metric])
                
                # Ensure attempts are in order
                while len(problem_attempts[problem_id]) < attempt_index:
                    problem_attempts[problem_id].append(0)
                
                if len(problem_attempts[problem_id]) == attempt_index - 1:
                    problem_attempts[problem_id].append(success)
                else:
                    problem_attempts[problem_id][attempt_index - 1] = success
    except Exception as e:
        if detailed:
            print(f"Error reading {attempts_file}: {e}")
        return None, []
    
    if not problem_attempts:
        if detailed:
            print(f"No data found in {attempts_file}")
        return None, []
    
    # Check if k is valid
    max_attempts = max(len(attempts) for attempts in problem_attempts.values())
    if k > max_attempts:
        if detailed:
            print(f"Skipping: k={k} > max attempts per problem={max_attempts}")
        return None, []
    
    # Calculate pass@k for each problem
    scores = []
    problem_results = []
    
    for problem_id, attempts in problem_attempts.items():
        n = len(attempts)  # Total attempts for this problem
        if n >= k:
            # Use ALL attempts to calculate unbiased pass@k estimator
            c = sum(attempts)  # Total successes out of n attempts
            score = pass_at_k(n, c, k)  # Use full formula with all attempts
            scores.append(score)
            problem_results.append((problem_id, n, c, score))
        else:
            if detailed:
                print(f"Problem {problem_id}: skipped (n={n} < k={k})")
    
    if not scores:
        if detailed:
            print(f"No valid problems for k={k}")
        return None, []
    
    avg_score = sum(scores) / len(scores)
    return avg_score, problem_results

def load_run_metadata(run_dir):
    """Load metadata from meta.json file."""
    meta_files = list(Path(run_dir).glob('*_meta.json'))
    if not meta_files:
        return {}
    
    try:
        with open(meta_files[0], 'r') as f:
            return json.load(f)
    except:
        return {}

def main():
    parser = argparse.ArgumentParser(description="Compute pass@k for all benchmark runs in a directory.")
    parser.add_argument('--dir', required=True, help="Directory containing benchmark run folders")
    parser.add_argument('--k', type=int, required=True, help="Value of k for pass@k")
    parser.add_argument('--detailed', action='store_true', help="Print detailed per-problem output")
    parser.add_argument('--metric', choices=['test_success', 'build_success', 'generation_success'],
                       default='test_success', help="Success metric to use (default: test_success)")
    
    args = parser.parse_args()
    
    base_dir = Path(args.dir)
    if not base_dir.exists():
        print(f"Error: Directory {args.dir} does not exist")
        sys.exit(1)
    
    print(f"Computing pass@{args.k} using metric '{args.metric}' for runs in {args.dir}")
    print("=" * 60)
    
    # Find all run directories
    run_dirs = []
    for item in base_dir.iterdir():
        if item.is_dir():
            # Check if this directory contains attempts CSV files
            attempts_files = list(item.glob('*_attempts.csv'))
            if attempts_files:
                run_dirs.append(item)
    
    if not run_dirs:
        print("No benchmark run directories found (looking for directories with *_attempts.csv files)")
        sys.exit(1)
    
    run_dirs.sort(key=lambda x: x.name)
    
    all_scores = []
    results_summary = []
    
    # Process each run directory
    for run_dir in run_dirs:
        # Find attempts file
        attempts_files = list(run_dir.glob('*_attempts.csv'))
        if not attempts_files:
            continue
        
        attempts_file = attempts_files[0]
        
        # Load metadata first
        metadata = load_run_metadata(run_dir)
        
        # Extract model name using metadata
        model_name = extract_model_name(run_dir.name, metadata)
        
        # Compute pass@k
        avg_score, problem_results = compute_pass_at_k_from_attempts(
            attempts_file, args.k, args.metric, args.detailed
        )
        
        if avg_score is not None:
            all_scores.append(avg_score)
            
            result_info = {
                'run_name': run_dir.name,
                'model': model_name,
                'pass_at_k': avg_score,
                'problems_evaluated': len(problem_results),
                'metadata': metadata
            }
            results_summary.append(result_info)
            
            # Print results
            if args.detailed:
                print(f"\n{'='*60}")
                print(f"Run: {run_dir.name}")
                print(f"Model: {model_name}")
                if metadata:
                    print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
                    print(f"Max K: {metadata.get('Kmax', 'N/A')}")
                print(f"Problems evaluated: {len(problem_results)}")
                
                print(f"\nPer-problem results:")
                for pid, n, c, score in sorted(problem_results, key=lambda x: int(x[0])):
                    print(f"  Problem {pid}: {c}/{args.k} successes (total attempts: {n}), pass@{args.k} = {score:.4f}")
                
                print(f"\nAverage pass@{args.k}: {avg_score:.4f}")
                print("-" * 60)
            else:
                print(f"{model_name}: pass@{args.k} = {avg_score:.4f} ({len(problem_results)} problems)")
    
    # Print overall summary
    if all_scores:
        print(f"\n{'='*60}")
        print(f"OVERALL SUMMARY - Pass@{args.k} using {args.metric}")
        print(f"{'='*60}")
        
        # Sort by performance
        results_summary.sort(key=lambda x: x['pass_at_k'], reverse=True)
        
        print("Model Performance Ranking:")
        for i, result in enumerate(results_summary, 1):
            print(f"{i:2d}. {result['model']:25s}: {result['pass_at_k']:.4f} ({result['problems_evaluated']} problems)")
        
        print(f"\nProcessed {len(all_scores)} runs")
        print(f"Average pass@{args.k} across all models: {sum(all_scores) / len(all_scores):.4f}")
        print(f"Best performance: {max(all_scores):.4f}")
        print(f"Worst performance: {min(all_scores):.4f}")
        print(f"Performance range: {max(all_scores) - min(all_scores):.4f}")
    else:
        print("No valid results found")

if __name__ == "__main__":
    main()