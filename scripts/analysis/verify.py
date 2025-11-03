#!/usr/bin/env python3
import csv, math, sys
from statistics import mean

def comb(n, k):
    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)

def unbiased_pass_at_k(n, c, k):
    if n <= 0 or c <= 0 or k > n:
        return 0.0
    return 1.0 - comb(n - c, k) / comb(n, k)

def get_k_list(headers, prefix):
    ks = []
    for h in headers:
        if h.startswith(prefix):
            try:
                ks.append(int(h.split("_")[-1]))
            except:
                pass
    return sorted(set(ks))

def to_float(x):
    try:
        return float(x)
    except:
        return None

def pct(x):
    return f"{100*x:.1f}%" if x is not None else "NA"

def main(path):
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        headers = r.fieldnames or []
        emp_ks = get_k_list(headers, "empirical_pass_at_")
        unb_ks = get_k_list(headers, "unbiased_pass_at_")

        # Accumulators for final summary
        macro_gen_rates, macro_bld_rates, macro_tst_rates = [], [], []
        macro_failed_build, macro_built_failed_test, macro_built_passed_test = [], [], []
        first_gen_list, first_bld_list, first_tst_list, task_succ_list = [], [], [], []

        # micro (pooled attempts)
        sum_gen_succ = sum_gen_att = 0
        sum_bld_succ = sum_bld_att = 0
        sum_tst_succ = sum_tst_att = 0

        # pass@k aggregates
        emp_k_values = {k: [] for k in emp_ks}
        unb_k_csv_values = {k: [] for k in unb_ks}   # from CSV
        unb_k_calc_values = {k: [] for k in unb_ks}  # recomputed

        print("\n=== Per-Problem Checks ===")
        for row in r:
            pid = row.get("problem_id", "")

            n_tot = int(row.get("total_attempts", 0))
            n_gen = int(row.get("generation_attempts", 0))
            s_gen = int(row.get("generation_successes", 0))
            n_bld = int(row.get("build_attempts", 0))
            s_bld = int(row.get("build_successes", 0))
            n_tst = int(row.get("test_attempts", 0))
            s_tst = int(row.get("test_successes", 0))

            r_gen_csv = to_float(row.get("generation_success_rate"))
            r_bld_csv = to_float(row.get("build_success_rate"))
            r_tst_csv = to_float(row.get("test_success_rate"))

            r_gen_calc = (s_gen / n_gen) if n_gen else None
            r_bld_calc = (s_bld / n_bld) if n_bld else None
            r_tst_calc = (s_tst / n_tst) if n_tst else None

            first_gen = row.get("first_generation_success")
            first_bld = row.get("first_build_success")
            first_tst = row.get("first_test_success")
            task_succ = row.get("task_success")

            print("="*72)
            print(f"Problem {pid}")
            print("- Rates (csv vs calc) -------------------------------")
            print(f"  generation_success_rate : {pct(r_gen_csv):>8}  | calc {pct(r_gen_calc):>8}")
            print(f"  build_success_rate      : {pct(r_bld_csv):>8}  | calc {pct(r_bld_calc):>8}")
            print(f"  test_success_rate       : {pct(r_tst_csv):>8}  | calc {pct(r_tst_calc):>8}")

            print("- First attempt --------------------------------------")
            print(f"  first_generation_success: {first_gen}")
            print(f"  first_build_success     : {first_bld}")
            print(f"  first_test_success      : {first_tst}")
            print(f"  task_success            : {task_succ}  (should equal first_test_success)")

            if emp_ks:
                print("- Empirical pass@k (CSV only) -----------------------")
                for k in emp_ks:
                    v = to_float(row.get(f"empirical_pass_at_{k}"))
                    print(f"  empirical_pass_at_{k:<2}: {v}")
                    if v is not None:
                        emp_k_values[k].append(v)

            if unb_ks:
                print("- Unbiased pass@k (csv vs calc) ---------------------")
                for k in unb_ks:
                    csv_v = to_float(row.get(f"unbiased_pass_at_{k}")) or 0.0
                    calc_v = unbiased_pass_at_k(n_tst, s_tst, k)
                    print(f"  unbiased_pass_at_{k:<2}: {csv_v:>7.4f}  | calc {calc_v:>7.4f}")
                    unb_k_csv_values[k].append(csv_v)
                    unb_k_calc_values[k].append(calc_v)

            # Decomposition from calc rates (per-attempt view)
            fb = 1 - (r_bld_calc or 0)
            bft = (r_bld_calc or 0) - (r_tst_calc or 0)
            bpt = (r_tst_calc or 0)
            print("- Decomposition (per-attempt, from calc rates) -------")
            print(f"  failed_build           : {pct(fb):>8}")
            print(f"  built_failed_test      : {pct(bft):>8}")
            print(f"  built_passed_test      : {pct(bpt):>8}")

            # Accumulate macro lists (ignore None)
            if r_gen_calc is not None: macro_gen_rates.append(r_gen_calc)
            if r_bld_calc is not None: macro_bld_rates.append(r_bld_calc)
            if r_tst_calc is not None: macro_tst_rates.append(r_tst_calc)
            macro_failed_build.append(fb)
            macro_built_failed_test.append(bft)
            macro_built_passed_test.append(bpt)

            # First-attempt lists
            if first_gen is not None and first_gen != "": first_gen_list.append(int(first_gen))
            if first_bld is not None and first_bld != "": first_bld_list.append(int(first_bld))
            if first_tst is not None and first_tst != "": first_tst_list.append(int(first_tst))
            if task_succ is not None and task_succ != "": task_succ_list.append(int(task_succ))

            # Micro sums
            sum_gen_succ += s_gen; sum_gen_att += n_gen
            sum_bld_succ += s_bld; sum_bld_att += n_bld
            sum_tst_succ += s_tst; sum_tst_att += n_tst

    # ----- Final Summary -----
    print("\n=== Final Summary ===")
    total_problems = len(macro_bld_rates)
    print(f"Problems: {total_problems}")

    # Macro averages (per-problem means)
    macro_gen = mean(macro_gen_rates) if macro_gen_rates else None
    macro_bld = mean(macro_bld_rates) if macro_bld_rates else None
    macro_tst = mean(macro_tst_rates) if macro_tst_rates else None

    print("\n- Macro averages (per-problem means) ------------------")
    print(f"  avg_generation_success_rate : {pct(macro_gen)}")
    print(f"  avg_build_success_rate      : {pct(macro_bld)}")
    print(f"  avg_test_success_rate       : {pct(macro_tst)}")

    # First-attempt rates
    first_gen_rate = mean(first_gen_list) if first_gen_list else None
    first_bld_rate = mean(first_bld_list) if first_bld_list else None
    first_tst_rate = mean(first_tst_list) if first_tst_list else None
    task_success_rate = mean(task_succ_list) if task_succ_list else None

    print("\n- First attempt (rates across problems) ---------------")
    print(f"  first_generation_success_rate: {pct(first_gen_rate)}")
    print(f"  first_build_success_rate     : {pct(first_bld_rate)}")
    print(f"  first_test_success_rate      : {pct(first_tst_rate)}")
    print(f"  task_success_rate            : {pct(task_success_rate)}  (should equal first_test_success_rate)")

    # Stage composition (macro)
    print("\n- Stage decomposition (macro per-attempt) -------------")
    print(f"  failed_build                 : {pct(mean(macro_failed_build))}")
    print(f"  compiled; tests failed       : {pct(mean(macro_built_failed_test))}")
    print(f"  compiled; tests passed       : {pct(mean(macro_built_passed_test))}")

    # Micro averages (pooled attempts)
    micro_gen = (sum_gen_succ / sum_gen_att) if sum_gen_att else None
    micro_bld = (sum_bld_succ / sum_bld_att) if sum_bld_att else None
    micro_tst = (sum_tst_succ / sum_tst_att) if sum_tst_att else None

    print("\n- Micro averages (pooled attempts) --------------------")
    print(f"  generation_success_rate      : {pct(micro_gen)}")
    print(f"  build_success_rate           : {pct(micro_bld)}")
    print(f"  test_success_rate            : {pct(micro_tst)}")

    # Conditional: pass given build (micro)
    cond_pass_given_build = (sum_tst_succ / sum_bld_succ) if sum_bld_succ else None
    print("\n- Conditional success (micro) ------------------------")
    print(f"  P(pass | compiled)           : {pct(cond_pass_given_build)}")

    # pass@k aggregates
    if emp_ks:
        print("\n- Empirical pass@k (macro mean of CSV values) --------")
        for k in emp_ks:
            vals = [v for v in emp_k_values[k] if v is not None]
            print(f"  empirical_pass_at_{k:<2}: {mean(vals):.4f}" if vals else f"  empirical_pass_at_{k:<2}: NA")

    if unb_ks:
        print("\n- Unbiased pass@k (csv vs calc, macro means) ---------")
        for k in unb_ks:
            csv_vals  = [v for v in unb_k_csv_values[k] if v is not None]
            calc_vals = [v for v in unb_k_calc_values[k] if v is not None]
            csv_mean  = mean(csv_vals)  if csv_vals  else None
            calc_mean = mean(calc_vals) if calc_vals else None
            print(f"  unbiased_pass_at_{k:<2}: csv {csv_mean:.4f} | calc {calc_mean:.4f}" if (csv_mean is not None and calc_mean is not None)
                  else f"  unbiased_pass_at_{k:<2}: csv {csv_mean} | calc {calc_mean}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 print_problem_metrics.py path/to/model_problems.csv")
        sys.exit(1)
    main(sys.argv[1])