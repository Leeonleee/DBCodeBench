import json
import os
import sys

# Usage: python tasks_to_json.py input.jsonl output_directory

input_jsonl = sys.argv[1]
output_dir = sys.argv[2]

# Make sure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Read the input JSONL file line-by-line
with open(input_jsonl, 'r') as f:
    for line in f:
        if not line.strip():
            continue  # Skip empty lines
        
        data = json.loads(line)
        pull_number = str(data["pull_number"])

        # Create a folder named by the pull number
        pr_folder = os.path.join(output_dir, pull_number)
        os.makedirs(pr_folder, exist_ok=True)

        # Write the JSON data inside the folder
        output_path = os.path.join(pr_folder, f"{pull_number}.json")
        with open(output_path, 'w') as out_f:
            json.dump(data, out_f, indent=2)

print(f"Finished splitting into folders under {output_dir}")
