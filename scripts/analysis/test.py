"""
Usage: python3 comprehensive_analysis.py --dir <directory> [--output <output_dir>] [--k <max_k>] [--detailed]

Comprehensive benchmark analysis that calculates:
1. Task success (first try success rate)
2. Pass@k (both unbiased estimator and empirical) for k=1 through k=max_k
3. Build success rates
4. Funnel analysis (generation → build → test)

Arguments:
  --dir: Directory containing benchmark run folders (required)
  --output: Output directory for CSV files (default: analysis_results)
  --k: Maximum k value for pass@k calculations (default: 10, calculates pass@1 through pass@k)
  --detailed: Print detailed progress information

Outputs individual CSV files for each model and a summary CSV.
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

def pass_at_k_unbiased(n, c, k):
    """Unbiased estimator for pass@k"""
    if c == 0 or k > n:
        return 0.0
    return 1.0 - comb(n - c, k) / comb(n, k)

def pass_at_k_empirical(attempts, k):
    """Empirical pass@k - direct measurement using first k attempts"""
    if len(attempts) < k:
        return None  # Not enough attempts
    
    first_k = attempts[:k]
    return 1.0 if sum(first_k) > 0 else 0.0

def extract_model_name(folder_name, metadata=None):
    """Extract a clean model name from metadata or folder name."""
    if metadata and 'model' in metadata:
        model = metadata['model']
        if model.startswith('openrouter/'):
            model = model.replace('openrouter/', '')
        if '/' in model:
            model = model.split('/')[-1]
        
        # If we have additional parameters in the folder name (like reasoning/thinking),
        # extract them and append to the model name
        parts = folder_name.split('_')
        additional_params = []
        found_model_part = False
        
        for i, part in enumerate(parts):
            # Skip timestamp parts
            if '-' in part and (len(part) == 10 or len(part) == 8):  # Date/time parts
                continue
            # Skip the k parameter
            if part.startswith('k') and part[1:].isdigit():
                break
            # Skip known provider prefixes
            if part in ['openrouter', 'openai', 'anthropic', 'google', 'gemini']:
                continue
            
            # Check if this part is the base model name or contains it
            base_model_clean = model.replace('-', '').replace('.', '').lower()
            part_clean = part.replace('-', '').replace('.', '').lower()
            
            if base_model_clean in part_clean or part_clean in base_model_clean:
                found_model_part = True
                continue
            
            # If we've found the model part, collect additional parameters
            # These could be reasoning levels, thinking token counts, etc.
            if found_model_part and not part.startswith('k'):
                additional_params.append(part)
        
        if additional_params:
            return f"{model}_{'-'.join(additional_params)}"
        return model
    
    # Fallback: extract from folder name
    parts = folder_name.split('_')
    if len(parts) >= 3:
        model_parts = []
        skip_first = True
        for part in parts:
            # Skip timestamp
            if skip_first:
                skip_first = False
                continue
            # Skip the k parameter
            if part.startswith('k') and part[1:].isdigit():
                break
            model_parts.append(part)
        
        if model_parts:
            model_name = '_'.join(model_parts)
            if model_name.startswith('openrouter_'):
                model_name = model_name.replace('openrouter_', '')
            return model_name
    
    return folder_name

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

def analyze_benchmark_run(attempts_file, k_max=10, detailed=False):
    """Comprehensive analysis of a single benchmark run."""
    if not os.path.exists(attempts_file):
        return None
    
    # Group attempts by problem
    problem_attempts = defaultdict(lambda: {
        'generation_success': [],
        'build_success': [],
        'test_success': []
    })
    
    try:
        with open(attempts_file, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                problem_id = row['problem']
                attempt_index = int(row['attempt_index'])
                
                # Ensure attempts are in order for each metric
                for metric in ['generation_success', 'build_success', 'test_success']:
                    while len(problem_attempts[problem_id][metric]) < attempt_index:
                        problem_attempts[problem_id][metric].append(0)
                    
                    success = int(row[metric])
                    if len(problem_attempts[problem_id][metric]) == attempt_index - 1:
                        problem_attempts[problem_id][metric].append(success)
                    else:
                        problem_attempts[problem_id][metric][attempt_index - 1] = success
    except Exception as e:
        if detailed:
            print(f"Error reading {attempts_file}: {e}")
        return None
    
    if not problem_attempts:
        return None
    
    # Calculate metrics for each problem
    results = []
    
    for problem_id, attempts in problem_attempts.items():
        n = len(attempts['test_success'])  # Total attempts
        
        if n == 0:
            continue
        
        problem_result = {
            'problem_id': problem_id,
            'total_attempts': n,
            
            # Generation success metrics
            'generation_attempts': len(attempts['generation_success']),
            'generation_successes': sum(attempts['generation_success']),
            'generation_success_rate': sum(attempts['generation_success']) / len(attempts['generation_success']) if attempts['generation_success'] else 0,
            
            # Build success metrics
            'build_attempts': len(attempts['build_success']),
            'build_successes': sum(attempts['build_success']),
            'build_success_rate': sum(attempts['build_success']) / len(attempts['build_success']) if attempts['build_success'] else 0,
            
            # Test success metrics
            'test_attempts': len(attempts['test_success']),
            'test_successes': sum(attempts['test_success']),
            'test_success_rate': sum(attempts['test_success']) / len(attempts['test_success']) if attempts['test_success'] else 0,
            
            # Task success (first try)
            'task_success': attempts['test_success'][0] if attempts['test_success'] else 0,
        }
        
        # Add empirical pass@k for k=1 to k_max
        for k in range(1, k_max + 1):
            problem_result[f'empirical_pass_at_{k}'] = pass_at_k_empirical(attempts['test_success'], k)
        
        # Add unbiased estimator pass@k for k=1 to k_max
        for k in range(1, k_max + 1):
            problem_result[f'unbiased_pass_at_{k}'] = pass_at_k_unbiased(n, sum(attempts['test_success']), k) if n >= k else None
        
        # Add funnel metrics
        problem_result.update({
            # Funnel metrics (first attempt)
            'first_generation_success': attempts['generation_success'][0] if attempts['generation_success'] else 0,
            'first_build_success': attempts['build_success'][0] if attempts['build_success'] else 0,
            'first_test_success': attempts['test_success'][0] if attempts['test_success'] else 0,
        })
        
        results.append(problem_result)
    
    return results

def calculate_aggregate_metrics(problem_results, k_max=10):
    """Calculate aggregate metrics across all problems."""
    if not problem_results:
        return {}
    
    total_problems = len(problem_results)
    
    # Filter out None values for metrics that might not be calculable
    def safe_mean(values):
        valid_values = [v for v in values if v is not None]
        return sum(valid_values) / len(valid_values) if valid_values else None
    
    aggregate = {
        'total_problems': total_problems,
        
        # Overall success rates
        'avg_generation_success_rate': safe_mean([p['generation_success_rate'] for p in problem_results]),
        'avg_build_success_rate': safe_mean([p['build_success_rate'] for p in problem_results]),
        'avg_test_success_rate': safe_mean([p['test_success_rate'] for p in problem_results]),
        
        # Task success (first try)
        'task_success_rate': sum(p['task_success'] for p in problem_results) / total_problems,
        
        # Funnel metrics
        'first_generation_success_rate': sum(p['first_generation_success'] for p in problem_results) / total_problems,
        'first_build_success_rate': sum(p['first_build_success'] for p in problem_results) / total_problems,
        'first_test_success_rate': sum(p['first_test_success'] for p in problem_results) / total_problems,
    }
    
    # Add empirical pass@k metrics for k=1 to k_max
    for k in range(1, k_max + 1):
        aggregate[f'empirical_pass_at_{k}'] = safe_mean([p[f'empirical_pass_at_{k}'] for p in problem_results])
    
    # Add unbiased pass@k metrics for k=1 to k_max
    for k in range(1, k_max + 1):
        aggregate[f'unbiased_pass_at_{k}'] = safe_mean([p[f'unbiased_pass_at_{k}'] for p in problem_results])
    
    return aggregate

def save_model_results(model_name, problem_results, aggregate_metrics, output_dir):
    """Save detailed results for a single model to CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save per-problem results
    problem_csv = output_dir / f"{model_name}_problems.csv"
    if problem_results:
        fieldnames = list(problem_results[0].keys())
        with open(problem_csv, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(problem_results)
    
    # Save aggregate metrics
    aggregate_csv = output_dir / f"{model_name}_summary.csv"
    with open(aggregate_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['metric', 'value'])
        writer.writerow(['model', model_name])
        for key, value in aggregate_metrics.items():
            writer.writerow([key, value])

def main():
    parser = argparse.ArgumentParser(description="Comprehensive benchmark analysis with CSV output.")
    parser.add_argument('--dir', required=True, help="Directory containing benchmark run folders")
    parser.add_argument('--output', default='analysis_results', help="Output directory for CSV files")
    parser.add_argument('--k', type=int, default=10, help="Maximum k value for pass@k calculations (calculates pass@1 through pass@k)")
    parser.add_argument('--detailed', action='store_true', help="Print detailed progress information")
    
    args = parser.parse_args()
    
    if args.k < 1:
        print("Error: --k must be at least 1")
        sys.exit(1)
    
    base_dir = Path(args.dir)
    if not base_dir.exists():
        print(f"Error: Directory {args.dir} does not exist")
        sys.exit(1)
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Analyzing benchmark runs in {args.dir}")
    print(f"Output directory: {output_dir}")
    print(f"Calculating pass@k for k=1 through k={args.k}")
    print("=" * 60)
    
    # Find all run directories
    run_dirs = []
    for item in base_dir.iterdir():
        if item.is_dir():
            attempts_files = list(item.glob('*_attempts.csv'))
            if attempts_files:
                run_dirs.append(item)
    
    if not run_dirs:
        print("No benchmark run directories found")
        sys.exit(1)
    
    run_dirs.sort(key=lambda x: x.name)
    
    all_model_results = []
    
    # Process each run directory
    for run_dir in run_dirs:
        attempts_files = list(run_dir.glob('*_attempts.csv'))
        if not attempts_files:
            continue
        
        attempts_file = attempts_files[0]
        metadata = load_run_metadata(run_dir)
        model_name = extract_model_name(run_dir.name, metadata)
        
        if args.detailed:
            print(f"Processing {model_name}...")
        
        # Analyze this run
        problem_results = analyze_benchmark_run(attempts_file, args.k, args.detailed)
        
        if problem_results:
            aggregate_metrics = calculate_aggregate_metrics(problem_results, args.k)
            aggregate_metrics['model'] = model_name
            aggregate_metrics['run_name'] = run_dir.name
            
            # Save model-specific results
            save_model_results(model_name, problem_results, aggregate_metrics, output_dir)
            
            all_model_results.append(aggregate_metrics)
            
            if args.detailed:
                print(f"  {model_name}: {aggregate_metrics['total_problems']} problems analyzed")
                print(f"    Task success rate: {aggregate_metrics['task_success_rate']:.3f}")
                for k in range(1, min(args.k + 1, 6)):  # Show first 5 pass@k values in detailed output
                    emp_key = f'empirical_pass_at_{k}'
                    if emp_key in aggregate_metrics and aggregate_metrics[emp_key] is not None:
                        print(f"    Empirical pass@{k}: {aggregate_metrics[emp_key]:.3f}")
                print(f"    Build success: {aggregate_metrics['first_build_success_rate']:.3f}")
        else:
            print(f"Failed to analyze {model_name}")
    
    # Save summary of all models
    if all_model_results:
        summary_csv = output_dir / "all_models_summary.csv"
        
        fieldnames = list(all_model_results[0].keys())
        with open(summary_csv, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_model_results)
        
        print(f"\nAnalysis complete!")
        print(f"Processed {len(all_model_results)} models")
        print(f"\nOutput files:")
        print(f"  Summary: {summary_csv}")
        
        for result in sorted(all_model_results, key=lambda x: x['task_success_rate'], reverse=True):
            model = result['model']
            print(f"  {model}: {output_dir}/{model}_problems.csv, {output_dir}/{model}_summary.csv")
        
        # Print quick comparison
        print(f"\nQuick comparison (Task Success Rate):")
        for i, result in enumerate(sorted(all_model_results, key=lambda x: x['task_success_rate'], reverse=True), 1):
            task_success = result['task_success_rate']
            emp_pass1 = result['empirical_pass_at_1']
            build_success = result['first_build_success_rate']
            print(f"{i:2d}. {result['model']:20s}: Task={task_success:.3f}, Pass@1={emp_pass1:.3f}, Build={build_success:.3f}")
        
        # Print pass@k comparison for all k values
        print(f"\nPass@k comparison (Empirical):")
        print(f"{'Model':<20}", end="")
        for k in range(1, args.k + 1):
            print(f"Pass@{k:<3}", end="")
        print()
        print("-" * (20 + 7 * args.k))
        
        for result in sorted(all_model_results, key=lambda x: x['task_success_rate'], reverse=True):
            print(f"{result['model']:<20}", end="")
            for k in range(1, args.k + 1):
                emp_key = f'empirical_pass_at_{k}'
                if emp_key in result and result[emp_key] is not None:
                    print(f"{result[emp_key]:.3f}  ", end="")
                else:
                    print("N/A   ", end="")
            print()
    
    else:
        print("No valid results found")

if __name__ == "__main__":
    main()