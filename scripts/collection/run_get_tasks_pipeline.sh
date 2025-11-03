#!/usr/bin/env bash

# If you'd like to parallelize, do the following:
# * Create a .env file in this folder
# * Declare GITHUB_TOKENS=token1,token2,token3...

python3 get_tasks_pipeline.py \
    --repos 'ClickHouse/ClickHouse' \
    --path_prs '/home/ec2-user/Documents/university/honours/scripts/collection/output/prs' \
    --path_tasks '/home/ec2-user/Documents/university/honours/scripts/collection/output/tasks'