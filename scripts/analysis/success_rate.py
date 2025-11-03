"""
Usage: python3 first_try_success.py --dir <directory> [--detailed] [--metric <metric>]
"""
import csv
import sys
import os
import json
import argparse
from pathlib import Path
from collections import defaultdict

def extract_model_name(folder_name, metadata=None):
    """Extract a clean model name from metadata or folder name."""
    # First try to get model name from metadata
    if metadata and 'model' in metadata:
        model = metadata['model']
        # Clean up common prefixes and paths
        if model.startswith('openrouter/'):
            model = model.replace('openrouter/', '')
        if '/' in model:
            # Take the last part if it's a path-like structure
            model = model.split('/')[-1]
        return model
    
    # Fallback: extract from folder name
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

def compute_first_try_success(attempts_file, metric='test_success', detailed=False):
    """Compute first try success rate from attempts CSV file."""
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
    
    # Calculate first try success for each problem
    successes = 0
    total_problems = 0
    problem_results = []
    
    for problem_id, attempts in problem_attempts.items():
        if len(attempts) >= 1:
            first_attempt_success = attempts[0]  # First attempt (index 0)
            total_problems += 1
            successes += first_attempt_success
            problem_results.append((problem_id, first_attempt_success))
        else:
            if detailed:
                print(f"Problem {problem_id}: no attempts found")
    
    if total_problems == 0:
        if detailed:
            print("No problems with attempts found")
        return None, []
    
    success_rate = successes / total_problems
    return success_rate, problem_results

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
    parser = argparse.ArgumentParser(description="Compute first try success rate for all benchmark runs in a directory.")
    parser.add_argument('--dir', required=True, help="Directory containing benchmark run folders")
    parser.add_argument('--detailed', action='store_true', help="Print detailed per-problem output")
    parser.add_argument('--metric', choices=['test_success', 'build_success', 'generation_success'],
                       default='test_success', help="Success metric to use (default: test_success)")
    
    args = parser.parse_args()
    
    base_dir = Path(args.dir)
    if not base_dir.exists():
        print(f"Error: Directory {args.dir} does not exist")
        sys.exit(1)
    
    print(f"Computing first try success rate using metric '{args.metric}' for runs in {args.dir}")
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
    
    all_success_rates = []
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
        
        # Compute first try success rate
        success_rate, problem_results = compute_first_try_success(
            attempts_file, args.metric, args.detailed
        )
        
        if success_rate is not None:
            all_success_rates.append(success_rate)
            
            result_info = {
                'run_name': run_dir.name,
                'model': model_name,
                'first_try_success_rate': success_rate,
                'problems_evaluated': len(problem_results),
                'successes': sum(result[1] for result in problem_results),
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
                print(f"First try successes: {sum(result[1] for result in problem_results)}")
                
                print(f"\nPer-problem results:")
                for pid, success in sorted(problem_results, key=lambda x: int(x[0])):
                    status = "SUCCESS" if success else "FAILED"
                    print(f"  Problem {pid}: {status}")
                
                print(f"\nFirst try success rate: {success_rate:.4f} ({success_rate*100:.1f}%)")
                print("-" * 60)
            else:
                print(f"{model_name}: {success_rate:.4f} ({success_rate*100:.1f}%) - {sum(result[1] for result in problem_results)}/{len(problem_results)} problems")
    
    # Print overall summary
    if all_success_rates:
        print(f"\n{'='*60}")
        print(f"OVERALL SUMMARY - First Try Success Rate using {args.metric}")
        print(f"{'='*60}")
        
        # Sort by performance
        results_summary.sort(key=lambda x: x['first_try_success_rate'], reverse=True)
        
        print("Model Performance Ranking:")
        for i, result in enumerate(results_summary, 1):
            success_rate = result['first_try_success_rate']
            successes = result['successes']
            total = result['problems_evaluated']
            print(f"{i:2d}. {result['model']:25s}: {success_rate:.4f} ({success_rate*100:5.1f}%) - {successes}/{total} problems")
        
        print(f"\nProcessed {len(all_success_rates)} runs")
        print(f"Average first try success rate: {sum(all_success_rates) / len(all_success_rates):.4f} ({sum(all_success_rates) / len(all_success_rates)*100:.1f}%)")
        print(f"Best performance: {max(all_success_rates):.4f} ({max(all_success_rates)*100:.1f}%)")
        print(f"Worst performance: {min(all_success_rates):.4f} ({min(all_success_rates)*100:.1f}%)")
        print(f"Performance range: {max(all_success_rates) - min(all_success_rates):.4f} ({(max(all_success_rates) - min(all_success_rates))*100:.1f} percentage points)")
    else:
        print("No valid results found")

if __name__ == "__main__":
    main()