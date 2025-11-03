
import os
import json
import re
import subprocess
import sys

# Usage: python process_single_pr.py path/to/pr_folder path/to/repo

pr_folder = sys.argv[1]
repo_path = sys.argv[2]
template_header = """You will be provided with a partial code base and an issue statement explaining a problem to resolve.

<issue>
"""
template_footer = """
</issue>

I need you to solve the provided issue by generating a code fix that can be applied directly to the repository

Respond below:
"""

# Extract pull number
pull_number = os.path.basename(pr_folder)
json_path = os.path.join(pr_folder, f"{pull_number}.json")

if not os.path.exists(json_path):
    print(f"ERROR: No JSON file found for PR {pull_number}")
    sys.exit(1)

with open(json_path) as f:
    instance = json.load(f)

base_commit = instance.get("base_commit")
if not base_commit:
    print(f"ERROR: No base_commit found in {pull_number}")
    sys.exit(1)

def git_checkout(commit_hash):
    subprocess.run(["git", "checkout", commit_hash], cwd=repo_path, check=True)

def git_checkout_back():
    subprocess.run(["git", "checkout", "-"], cwd=repo_path, check=True)

def extract_modified_files_from_patch(patch_path):
    try:
        result = subprocess.run(
            ["lsdiff", patch_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        # Strip leading "a/" if present
        return [line.strip()[2:] if line.startswith("a/") else line.strip() for line in result.stdout.splitlines()]
    except subprocess.CalledProcessError as e:
        print(f"ERROR: lsdiff failed on {patch_path}: {e.stderr}")
        return []

def build_simple_prompt(instance):
    issue = instance["problem_statement"].strip()
    return f"{template_header}{issue}{template_footer}"

print(f"Processing {pull_number}...")

try:
    git_checkout(base_commit)

    # Save fix.patch
    fix_patch_path = None
    if "patch" in instance:
        fix_patch_path = os.path.join(pr_folder, "fix.patch")
        with open(fix_patch_path, 'w') as f:
            f.write(instance["patch"].replace('\\n', '\n'))

    # Save test.patch
    test_patch_path = None
    if "test_patch" in instance:
        test_patch_path = os.path.join(pr_folder, "test.patch")
        with open(test_patch_path, 'w') as f:
            f.write(instance["test_patch"].replace('\\n', '\n'))

    # Extract modified files and update JSON
    if fix_patch_path and os.path.exists(fix_patch_path):
        instance["modified_files"] = extract_modified_files_from_patch(fix_patch_path)

    if test_patch_path and os.path.exists(test_patch_path):
        instance["modified_test_files"] = extract_modified_files_from_patch(test_patch_path)

    with open(json_path, 'w') as f:
        json.dump(instance, f, indent=2)

    # Save simplified Aider-style prompt
    prompt_text = build_simple_prompt(instance)
    prompt_path = os.path.join(pr_folder, f"{pull_number}.prompt")
    with open(prompt_path, 'w') as f:
        f.write(prompt_text)

except subprocess.CalledProcessError as e:
    print(f"ERROR: Git checkout failed: {e}")
finally:
    git_checkout_back()

print(f"✅ Finished processing {pull_number}.")