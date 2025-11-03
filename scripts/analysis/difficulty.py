"""
Problem Difficulty Classifier

Classifies benchmark problems by difficulty based on:
1. Size of the fix diff (lines added/removed)
2. Number of files touched in modified_files
3. Number of tests modified in modified_test_files

Usage: python classify_problems.py <benchmark_dir> [--output results.csv] [--detailed]
"""

import argparse
import json
import sys
import csv
import re
from pathlib import Path
from collections import defaultdict
from statistics import median


def parse_diff_stats(diff_content):
    """
    Parse a unified diff to count lines added, removed, and changed files.
    
    Returns: dict with 'lines_added', 'lines_removed', 'files_changed'
    """
    if not diff_content:
        return {'lines_added': 0, 'lines_removed': 0, 'files_changed': 0}
    
    lines_added = 0
    lines_removed = 0
    files_changed = set()
    
    for line in diff_content.split('\n'):
        # Track files being modified
        if line.startswith('diff --git'):
            # Extract file paths from "diff --git a/file b/file"
            match = re.search(r'diff --git a/(.*?) b/(.*?)$', line)
            if match:
                files_changed.add(match.group(1))
        elif line.startswith('+++') or line.startswith('---'):
            # Alternative way to track files
            match = re.search(r'[+-]{3} [ab]/(.*?)$', line)
            if match and not match.group(1).startswith('/dev/null'):
                files_changed.add(match.group(1))
        elif line.startswith('+') and not line.startswith('+++'):
            # Line added
            lines_added += 1
        elif line.startswith('-') and not line.startswith('---'):
            # Line removed
            lines_removed += 1
    
    return {
        'lines_added': lines_added,
        'lines_removed': lines_removed,
        'lines_changed': lines_added + lines_removed,
        'files_changed': len(files_changed)
    }


def load_problem_data(problem_dir):
    """
    Load problem data from a problem directory.
    
    Returns: dict with problem metadata and diff stats
    """
    problem_path = Path(problem_dir)
    problem_id = problem_path.name
    
    # Load JSON metadata
    json_file = problem_path / f"{problem_id}.json"
    if not json_file.exists():
        return None
    
    try:
        with open(json_file, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"Error loading {json_file}: {e}")
        return None
    
    # Load fix.patch if it exists
    fix_patch_file = problem_path / "fix.patch"
    fix_diff_content = ""
    if fix_patch_file.exists():
        try:
            with open(fix_patch_file, 'r') as f:
                fix_diff_content = f.read()
        except Exception as e:
            print(f"Warning: Could not read {fix_patch_file}: {e}")
    else:
        # Fallback to patch field in JSON
        fix_diff_content = metadata.get('patch', '')
    
    # Parse diff statistics
    diff_stats = parse_diff_stats(fix_diff_content)
    
    # Get file and test counts from metadata
    modified_files = metadata.get('modified_files', [])
    modified_test_files = metadata.get('modified_test_files', [])
    
    return {
        'problem_id': problem_id,
        'repo': metadata.get('repo', ''),
        'pull_number': metadata.get('pull_number', ''),
        'instance_id': metadata.get('instance_id', ''),
        'created_at': metadata.get('created_at', ''),
        
        # Difficulty metrics
        'lines_added': diff_stats['lines_added'],
        'lines_removed': diff_stats['lines_removed'],
        'lines_changed': diff_stats['lines_changed'],
        'files_changed_in_diff': diff_stats['files_changed'],
        'files_in_modified_files': len(modified_files),
        'test_files_modified': len(modified_test_files),
        
        # Raw data for reference
        'modified_files': modified_files,
        'modified_test_files': modified_test_files,
        
        # Additional context
        'issue_numbers': metadata.get('issue_numbers', []),
        'base_commit': metadata.get('base_commit', ''),
    }


def classify_difficulty(problem_data):
    """
    Classify problem difficulty based on multiple metrics.
    
    Returns: difficulty level (1-5) and reasoning
    """
    lines_changed = problem_data['lines_changed']
    files_touched = max(problem_data['files_changed_in_diff'], problem_data['files_in_modified_files'])
    test_files = problem_data['test_files_modified']
    
    # Calculate weighted difficulty score
    score = 0
    reasons = []
    
    # Lines changed scoring (0-3 points)
    if lines_changed == 0:
        score += 0
        reasons.append("No code changes")
    elif lines_changed <= 5:
        score += 1
        reasons.append(f"Minimal changes ({lines_changed} lines)")
    elif lines_changed <= 20:
        score += 2
        reasons.append(f"Small changes ({lines_changed} lines)")
    elif lines_changed <= 50:
        score += 3
        reasons.append(f"Medium changes ({lines_changed} lines)")
    else:
        score += 4
        reasons.append(f"Large changes ({lines_changed} lines)")
    
    # Files touched scoring (0-2 points)
    if files_touched == 0:
        score += 0
    elif files_touched == 1:
        score += 1
        reasons.append("Single file")
    elif files_touched <= 3:
        score += 2
        reasons.append(f"Multiple files ({files_touched})")
    else:
        score += 3
        reasons.append(f"Many files ({files_touched})")
    
    # Test files scoring (0-2 points)
    if test_files == 0:
        score += 0
        reasons.append("No test changes")
    elif test_files == 1:
        score += 1
        reasons.append("Single test file")
    else:
        score += 2
        reasons.append(f"Multiple test files ({test_files})")
    
    # Convert score to difficulty level (1-5)
    if score == 0:
        difficulty = 1
        level_desc = "Trivial"
    elif score <= 2:
        difficulty = 1
        level_desc = "Very Easy"
    elif score <= 4:
        difficulty = 2
        level_desc = "Easy"
    elif score <= 6:
        difficulty = 3
        level_desc = "Medium"
    elif score <= 8:
        difficulty = 4
        level_desc = "Hard"
    else:
        difficulty = 5
        level_desc = "Very Hard"
    
    return {
        'difficulty_level': difficulty,
        'difficulty_desc': level_desc,
        'difficulty_score': score,
        'reasoning': "; ".join(reasons)
    }


def analyze_benchmark(benchmark_dir, output_file=None, detailed=False):
    """
    Analyze all problems in a benchmark directory.
    """
    benchmark_path = Path(benchmark_dir)
    if not benchmark_path.exists():
        print(f"Error: Benchmark directory '{benchmark_dir}' not found.")
        return
    
    print(f"Analyzing benchmark directory: {benchmark_path}")
    print("=" * 60)
    
    # Find all problem directories (directories with numeric names)
    problem_dirs = []
    for item in benchmark_path.iterdir():
        if item.is_dir() and item.name.isdigit():
            problem_dirs.append(item)
    
    if not problem_dirs:
        print("No problem directories found (looking for numeric directory names)")
        return
    
    problem_dirs.sort(key=lambda x: int(x.name))
    print(f"Found {len(problem_dirs)} problems")
    
    # Analyze each problem
    all_problems = []
    difficulty_counts = defaultdict(int)
    
    for problem_dir in problem_dirs:
        problem_data = load_problem_data(problem_dir)
        if problem_data is None:
            print(f"Skipping {problem_dir.name}: could not load data")
            continue
        
        # Classify difficulty
        difficulty_info = classify_difficulty(problem_data)
        problem_data.update(difficulty_info)
        
        all_problems.append(problem_data)
        difficulty_counts[difficulty_info['difficulty_level']] += 1
        
        if detailed:
            print(f"\nProblem {problem_data['problem_id']}:")
            print(f"  Difficulty: Level {difficulty_info['difficulty_level']} ({difficulty_info['difficulty_desc']})")
            print(f"  Lines changed: +{problem_data['lines_added']}, -{problem_data['lines_removed']} (total: {problem_data['lines_changed']})")
            print(f"  Files touched: {max(problem_data['files_changed_in_diff'], problem_data['files_in_modified_files'])}")
            print(f"  Test files: {problem_data['test_files_modified']}")
            print(f"  Reasoning: {difficulty_info['reasoning']}")
    
    # Display summary statistics
    print(f"\n{'='*60}")
    print("DIFFICULTY DISTRIBUTION")
    print(f"{'='*60}")
    
    total_problems = len(all_problems)
    for level in range(1, 6):
        count = difficulty_counts[level]
        percentage = (count / total_problems * 100) if total_problems > 0 else 0
        level_names = {1: "Very Easy", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Very Hard"}
        print(f"Level {level} ({level_names[level]:10s}): {count:3d} problems ({percentage:5.1f}%)")
    
    print(f"\nTotal problems analyzed: {total_problems}")
    
    # Detailed breakdowns by individual metrics
    if all_problems:
        lines_changed = [p['lines_changed'] for p in all_problems]
        files_touched = [max(p['files_changed_in_diff'], p['files_in_modified_files']) for p in all_problems]
        test_files = [p['test_files_modified'] for p in all_problems]
        
        print(f"\n{'='*60}")
        print("LINES CHANGED DISTRIBUTION")
        print(f"{'='*60}")
        
        # Lines changed buckets
        lines_buckets = defaultdict(list)
        for problem in all_problems:
            lines = problem['lines_changed']
            problem_id = problem['problem_id']
            if lines == 0:
                bucket = "0 lines"
            elif lines <= 5:
                bucket = "1-5 lines"
            elif lines <= 10:
                bucket = "6-10 lines"
            elif lines <= 20:
                bucket = "11-20 lines"
            elif lines <= 50:
                bucket = "21-50 lines"
            elif lines <= 100:
                bucket = "51-100 lines"
            else:
                bucket = "100+ lines"
            lines_buckets[bucket].append(problem_id)
        
        bucket_order = ["0 lines", "1-5 lines", "6-10 lines", "11-20 lines", "21-50 lines", "51-100 lines", "100+ lines"]
        for bucket in bucket_order:
            problems = lines_buckets[bucket]
            count = len(problems)
            percentage = (count / total_problems * 100) if total_problems > 0 else 0
            print(f"{bucket:12s}: {count:3d} problems ({percentage:5.1f}%)")
            if detailed:
                print(f"             Problems: {', '.join(sorted(problems, key=int))}")
        
        print(
            f"Mean: {sum(lines_changed)/len(lines_changed):.1f}, "
            f"Median: {median(lines_changed):.1f}, "
            f"Min: {min(lines_changed)}, Max: {max(lines_changed)}"
        )
        
        print(f"\n{'='*60}")
        print("FILES TOUCHED DISTRIBUTION")
        print(f"{'='*60}")
        
        # Files touched buckets
        files_buckets = defaultdict(list)
        for problem in all_problems:
            files = max(problem['files_changed_in_diff'], problem['files_in_modified_files'])
            problem_id = problem['problem_id']
            if files == 0:
                bucket = "0 files"
            elif files == 1:
                bucket = "1 file"
            elif files <= 3:
                bucket = "2-3 files"
            elif files <= 5:
                bucket = "4-5 files"
            elif files <= 10:
                bucket = "6-10 files"
            else:
                bucket = "10+ files"
            files_buckets[bucket].append(problem_id)
        
        bucket_order = ["0 files", "1 file", "2-3 files", "4-5 files", "6-10 files", "10+ files"]
        for bucket in bucket_order:
            problems = files_buckets[bucket]
            count = len(problems)
            percentage = (count / total_problems * 100) if total_problems > 0 else 0
            print(f"{bucket:12s}: {count:3d} problems ({percentage:5.1f}%)")
            if detailed:
                print(f"             Problems: {', '.join(sorted(problems, key=int))}")
        
        print(
            f"Mean: {sum(files_touched)/len(files_touched):.1f}, "
            f"Median: {median(files_touched):.1f}, "
            f"Min: {min(files_touched)}, Max: {max(files_touched)}"
        )
        
        print(f"\n{'='*60}")
        print("TEST FILES MODIFIED DISTRIBUTION")
        print(f"{'='*60}")
        
        # Test files buckets
        test_buckets = defaultdict(list)
        for problem in all_problems:
            tests = problem['test_files_modified']
            problem_id = problem['problem_id']
            if tests == 0:
                bucket = "0 tests"
            elif tests == 1:
                bucket = "1 test"
            elif tests <= 3:
                bucket = "2-3 tests"
            elif tests <= 5:
                bucket = "4-5 tests"
            else:
                bucket = "5+ tests"
            test_buckets[bucket].append(problem_id)
        
        bucket_order = ["0 tests", "1 test", "2-3 tests", "4-5 tests", "5+ tests"]
        for bucket in bucket_order:
            problems = test_buckets[bucket]
            count = len(problems)
            percentage = (count / total_problems * 100) if total_problems > 0 else 0
            print(f"{bucket:12s}: {count:3d} problems ({percentage:5.1f}%)")
            if detailed:
                print(f"             Problems: {', '.join(sorted(problems, key=int))}")
        
        print(
            f"Mean: {sum(test_files)/len(test_files):.1f}, "
            f"Median: {median(test_files):.1f}, "
            f"Min: {min(test_files)}, Max: {max(test_files)}"
        )

        # Optional: summarize difficulty scores too
        diff_scores = [p['difficulty_score'] for p in all_problems]
        print(f"\n{'='*60}")
        print("DIFFICULTY SCORE SUMMARY")
        print(f"{'='*60}")
        print(
            f"Mean: {sum(diff_scores)/len(diff_scores):.2f}, "
            f"Median: {median(diff_scores):.2f}, "
            f"Min: {min(diff_scores)}, Max: {max(diff_scores)}"
        )
    
    # Export to CSV if requested
    if output_file:
        fieldnames = [
            'problem_id', 'difficulty_level', 'difficulty_desc', 'difficulty_score',
            'lines_added', 'lines_removed', 'lines_changed',
            'files_changed_in_diff', 'files_in_modified_files', 'test_files_modified',
            'reasoning', 'repo', 'pull_number', 'created_at'
        ]
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for problem in all_problems:
                row = {field: problem.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        print(f"\nResults exported to {output_file}")
    
    return all_problems



def main():
    parser = argparse.ArgumentParser(
        description="Classify benchmark problems by difficulty",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python classify_problems.py duckdb_benchmark/
  python classify_problems.py duckdb_benchmark/ --output difficulty_analysis.csv
  python classify_problems.py duckdb_benchmark/ --detailed --output results.csv
        """
    )
    
    parser.add_argument('benchmark_dir', help='Path to benchmark directory')
    parser.add_argument('--output', help='Output CSV file for results')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed analysis for each problem')
    
    args = parser.parse_args()
    
    if not args.benchmark_dir:
        parser.print_help()
        sys.exit(1)
    
    analyze_benchmark(args.benchmark_dir, args.output, args.detailed)


if __name__ == "__main__":
    main()