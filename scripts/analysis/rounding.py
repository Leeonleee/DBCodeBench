
import pandas as pd

# Load CSV
df = pd.read_csv("analysis_results/all_models_summary.csv")

# Columns that represent pass@k values
passk_cols = [
    "empirical_pass_at_1", "empirical_pass_at_2", "empirical_pass_at_3",
    "empirical_pass_at_4", "empirical_pass_at_5",
    "unbiased_pass_at_1", "unbiased_pass_at_2", "unbiased_pass_at_3",
    "unbiased_pass_at_4", "unbiased_pass_at_5"
]

# Round pass@k values to 2 decimal places
df[passk_cols] = df[passk_cols].round(2)

# Other rate columns (convert to percentage, 1 decimal place)
rate_cols = [
    "avg_generation_success_rate", "avg_build_success_rate", "avg_test_success_rate",
    "task_success_rate", "first_generation_success_rate", "first_build_success_rate",
    "first_test_success_rate"
]

df[rate_cols] = (df[rate_cols] * 100).round(1)

# Save to new CSV
df.to_csv("analysis_results/all_models_summary_rounded.csv", index=False)

print("Saved cleaned results to results_cleaned.csv")