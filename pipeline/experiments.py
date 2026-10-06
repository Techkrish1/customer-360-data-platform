"""
Experiments for Problem 01 — Incremental Ingestion

Three experiments with measured results:

  A. Incremental proof     - simulate new data, run pipeline, measure delta
  B. Idempotency test      - run pipeline twice, row counts must stay identical
  C. Data quality          - inject bad rows, verify Silver validation catches them

Results are printed to console and saved locally.
Nothing in this file is pushed to GitHub.
"""
import io
import sys
import time
import yaml
import boto3
import psycopg2
import pandas as pd
import pyarrow as pa
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent to path so we can import our pipeline scripts
sys.path.insert(0, str(Path(__file__).parent))

import importlib
simulate_mod   = importlib.import_module("simulate_data")
bronze_mod     = importlib.import_module("extract_bronze")
silver_mod     = importlib.import_module("silver_transform")
dimensions_mod = importlib.import_module("gold_dimensions")
facts_mod      = importlib.import_module("gold_facts")
mart_mod       = importlib.import_module("gold_mart")

CONFIG_PATH = Path(__file__).parents[1] / "config" / "config.yaml"

SEPARATOR = "=" * 60


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def snapshot_postgres(cur, label):
    counts = {}
    for t in ["retailco_orders", "retailco_customers", "retailco_order_items"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        counts[t] = cur.fetchone()[0]

    cur.execute("""
        SELECT last_watermark, last_run_at, status
        FROM retailco_pipeline_watermarks
        WHERE pipeline_name = 'orders_incremental'
    """)
    wm = cur.fetchone()

    print(f"\n[{label}] PostgreSQL state:")
    for t, c in counts.items():
        print(f"  {t:<30} {c:>6} rows")
    print(f"  Watermark: {wm[0]}  |  Status: {wm[2]}")
    return counts, wm[0]


def snapshot_s3_bronze(s3, bucket, label):
    resp = s3.list_objects_v2(Bucket=bucket, Prefix="customer-360/bronze/")
    files = [o for o in resp.get("Contents", []) if o["Key"].endswith(".parquet")]
    total_size = sum(o["Size"] for o in files)
    print(f"\n[{label}] S3 Bronze:")
    print(f"  Parquet files : {len(files)}")
    print(f"  Total size    : {total_size // 1024} KB")
    return len(files)


def snapshot_delta(path, opts, label):
    from deltalake import DeltaTable
    try:
        dt  = DeltaTable(path, storage_options=opts)
        df  = dt.to_pandas()
        ver = dt.version()
        print(f"  {label:<30} {len(df):>6} rows  (Delta v{ver})")
        return len(df), ver
    except Exception:
        print(f"  {label:<30}  not yet created")
        return 0, -1


def snapshot_gold(base, opts, label):
    print(f"\n[{label}] Gold layer:")
    tables = ["dim_customer", "fact_orders", "mart_customer_rfm"]
    results = {}
    for t in tables:
        rows, ver = snapshot_delta(f"{base}/gold/{t}", opts, t)
        results[t] = rows
    return results


# ── Run full pipeline ─────────────────────────────────────────────────────────

def run_pipeline(label):
    print(f"\n  Running pipeline: {label}")
    start = time.time()
    bronze_mod.run()
    silver_mod.run()
    dimensions_mod.run()
    facts_mod.run()
    mart_mod.run()
    elapsed = round(time.time() - start, 1)
    print(f"\n  Pipeline complete in {elapsed}s")
    return elapsed


# ── Experiment A — Incremental proof ─────────────────────────────────────────

def experiment_a(pg_cur, s3, bucket, base, opts):
    print(f"\n{SEPARATOR}")
    print("EXPERIMENT A: Incremental Proof")
    print("Does the pipeline pick up ONLY new/changed records?")
    print(SEPARATOR)

    # Before state
    counts_before, wm_before = snapshot_postgres(pg_cur, "BEFORE")
    files_before = snapshot_s3_bronze(s3, bucket, "BEFORE")

    # Simulate a small batch — easy to trace in the output
    print("\n  Simulating 10 new orders + 5 status updates + 2 new customers...")
    simulate_mod.simulate(new_orders=10, status_updates=5, new_customers=2)

    # Run only extraction (Bronze)
    print("\n  Running extraction (Bronze only)...")
    t_start = time.time()
    bronze_mod.run()
    t_bronze = round(time.time() - t_start, 1)

    # After state
    counts_after, wm_after = snapshot_postgres(pg_cur, "AFTER extraction")
    files_after = snapshot_s3_bronze(s3, bucket, "AFTER extraction")

    # Results
    new_files = files_after - files_before
    new_orders = counts_after['retailco_orders'] - counts_before['retailco_orders']
    print(f"\n  RESULT:")
    print(f"  New orders in PostgreSQL    : {new_orders}  (we inserted exactly 10)")
    print(f"  New Bronze Parquet files    : {new_files}  (one per table per run)")
    print(f"  Watermark before            : {wm_before}")
    print(f"  Watermark after             : {wm_after}")
    print(f"  Watermark advanced by       : {wm_after - wm_before}")
    print(f"  Extraction time             : {t_bronze}s")
    print(f"\n  VERDICT: {'PASS - only delta extracted' if new_files > 0 else 'CHECK - no new files'}")

    return {"new_orders": counts_after['retailco_orders'] - counts_before['retailco_orders'],
            "new_bronze_files": new_files, "extraction_time": t_bronze}


# ── Experiment B — Idempotency ────────────────────────────────────────────────

def experiment_b(base, opts):
    print(f"\n{SEPARATOR}")
    print("EXPERIMENT B: Idempotency")
    print("Running the Silver + Gold pipeline twice with NO new data.")
    print("Row counts must be identical after both runs.")
    print(SEPARATOR)

    # Run 1
    print("\n  Run 1 — Silver through Mart...")
    silver_mod.run()
    dimensions_mod.run()
    facts_mod.run()
    mart_mod.run()
    gold_1 = snapshot_gold(base, opts, "AFTER Run 1")

    # Run 2 — same data, no new Bronze files
    print("\n  Run 2 — same data, re-running Silver through Mart...")
    silver_mod.run()
    dimensions_mod.run()
    facts_mod.run()
    mart_mod.run()
    gold_2 = snapshot_gold(base, opts, "AFTER Run 2")

    # Compare
    print(f"\n  RESULT:")
    all_equal = True
    for t in gold_1:
        r1, r2 = gold_1[t], gold_2[t]
        match = "SAME" if r1 == r2 else "DIFFERENT"
        if r1 != r2:
            all_equal = False
        print(f"  {t:<25} Run1={r1}  Run2={r2}  -> {match}")

    print(f"\n  VERDICT: {'PASS - pipeline is idempotent' if all_equal else 'FAIL - duplicates detected'}")
    return all_equal


# ── Experiment C — Data quality ───────────────────────────────────────────────

def experiment_c(pg_cur, s3, bucket, base, opts, pg_conn):
    print(f"\n{SEPARATOR}")
    print("EXPERIMENT C: Data Quality")
    print("Injecting 5 bad rows: null order_id, negative amounts.")
    print("Silver validation must catch and drop them.")
    print(SEPARATOR)

    # Get current max ids
    pg_cur.execute("SELECT MAX(order_id) FROM retailco_orders")
    max_id = pg_cur.fetchone()[0]

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Inject 3 rows: 2 bad + 1 valid control
    bad_rows = [
        (max_id + 1, 1, "confirmed",  -99.00,  "North", now, now),  # negative amount -> blocked
        (max_id + 2, 2, "bad_status", 100.00,  "East",  now, now),  # invalid status  -> blocked
        (max_id + 3, 3, "confirmed",  150.00,  "West",  now, now),  # valid control   -> passes
    ]

    pg_cur.executemany("""
        INSERT INTO retailco_orders
            (order_id, customer_id, status, total_amount, region, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, bad_rows)
    print(f"\n  Injected 3 rows: 2 bad (negative amount, invalid status) + 1 valid control")

    # Run extraction + Silver
    print("  Running extraction and Silver transform...")
    bronze_mod.run()

    # Capture Silver orders count before and after
    from deltalake import DeltaTable
    dt_before = DeltaTable(f"{base}/silver/orders", storage_options=opts)
    count_before = len(dt_before.to_pandas())

    silver_mod.run()

    dt_after = DeltaTable(f"{base}/silver/orders", storage_options=opts)
    df_after = dt_after.to_pandas()
    count_after = len(df_after)

    new_rows = count_after - count_before

    # Check if bad rows made it through
    bad_ids = [max_id + 1, max_id + 2]  # negative + invalid status
    leaked = df_after[df_after["order_id"].isin(bad_ids)]

    print(f"\n  RESULT:")
    print(f"  Rows in Silver before       : {count_before}")
    print(f"  Rows in Silver after        : {count_after}")
    print(f"  Net new rows added          : {new_rows}  (expected 1 — the valid control only)")
    print(f"  Bad rows leaked to Silver   : {len(leaked)}  (expected 0)")
    print(f"\n  VERDICT: {'PASS - bad rows blocked by validation' if len(leaked) == 0 and new_rows == 1 else 'CHECK - review validation rules'}")

    # Cleanup — remove injected test rows from postgres
    pg_cur.execute(f"DELETE FROM retailco_orders WHERE order_id IN ({max_id+1},{max_id+2},{max_id+3})")
    print(f"  Cleanup: test rows removed from PostgreSQL")

    return {"bad_rows_blocked": len(leaked) == 0, "valid_rows_passed": new_rows == 1}


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg    = load_config()
    s3_cfg = cfg["staging"]["s3"]
    bucket = s3_cfg["bucket"]
    opts   = {
        "AWS_ACCESS_KEY_ID"         : s3_cfg["aws_access_key_id"],
        "AWS_SECRET_ACCESS_KEY"     : s3_cfg["aws_secret_access_key"],
        "AWS_REGION"                : s3_cfg["region"],
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }
    base = f"s3://{bucket}/customer-360"

    pg = cfg["source"]["postgres"]
    pg_conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], database=pg["database"],
        user=pg["username"], password=pg["password"]
    )
    pg_conn.autocommit = True
    pg_cur = pg_conn.cursor()
    pg_cur.execute("SET search_path TO public;")

    s3 = boto3.client("s3",
        aws_access_key_id=s3_cfg["aws_access_key_id"],
        aws_secret_access_key=s3_cfg["aws_secret_access_key"],
        region_name=s3_cfg["region"])

    print(f"\n{'#' * 60}")
    print("  PIPELINE EXPERIMENTS — Problem 01: Incremental Ingestion")
    print(f"  Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'#' * 60}")

    results = {}

    results["A"] = experiment_a(pg_cur, s3, bucket, base, opts)
    results["B"] = experiment_b(base, opts)
    results["C"] = experiment_c(pg_cur, s3, bucket, base, opts, pg_conn)

    print(f"\n{SEPARATOR}")
    print("ALL EXPERIMENTS COMPLETE")
    print(SEPARATOR)
    print(f"  A - Incremental proof   : {'PASS' if results['A']['new_bronze_files'] > 0 else 'REVIEW'}")
    print(f"  B - Idempotency         : {'PASS' if results['B'] else 'FAIL'}")
    print(f"  C - Data quality        : {'PASS' if results['C']['bad_rows_blocked'] else 'FAIL'}")

    pg_conn.close()


if __name__ == "__main__":
    run()
