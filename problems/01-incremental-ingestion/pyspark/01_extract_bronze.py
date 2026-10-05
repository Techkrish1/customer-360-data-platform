"""
Script 01: Incremental extraction from PostgreSQL → S3 Bronze.

Flow:
  1. Read watermark from PostgreSQL
  2. Calculate extraction window: (watermark - 15 min overlap) → batch_end
  3. Extract changed records from all three source tables
  4. Write raw Parquet to S3 Bronze (partitioned by date)
  5. Update watermark — ONLY after all S3 writes confirmed
"""
import io
import sys
import yaml
import boto3
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"

PIPELINE_NAME  = "orders_incremental"
OVERLAP_MINUTES = 15

TABLES = [
    "retailco_orders",
    "retailco_customers",
    "retailco_order_items",
]


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── PostgreSQL ────────────────────────────────────────────────────────────────

def get_pg_connection(cfg):
    pg = cfg["source"]["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], database=pg["database"],
        user=pg["username"], password=pg["password"]
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO public;")
    return conn, cur


def read_watermark(cur):
    cur.execute("""
        SELECT last_watermark FROM retailco_pipeline_watermarks
        WHERE pipeline_name = %s
    """, (PIPELINE_NAME,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No watermark found for pipeline '{PIPELINE_NAME}'")
    return row[0]


def update_watermark(cur, batch_end):
    cur.execute("""
        UPDATE retailco_pipeline_watermarks
        SET last_watermark = %s,
            last_run_at    = %s,
            status         = 'success'
        WHERE pipeline_name = %s
    """, (batch_end, datetime.now(timezone.utc).replace(tzinfo=None), PIPELINE_NAME))
    print(f"  Watermark updated to {batch_end}")


def extract_table(cur, table, window_start, batch_end):
    query = f"""
        SELECT *
        FROM {table}
        WHERE updated_at > %s
          AND updated_at <= %s
        ORDER BY updated_at
    """
    cur.execute(query, (window_start, batch_end))
    columns = [desc[0] for desc in cur.description]
    rows    = cur.fetchall()
    df = pd.DataFrame(rows, columns=columns)
    return df


# ── S3 ────────────────────────────────────────────────────────────────────────

def get_s3_client(cfg):
    s3_cfg = cfg["staging"]["s3"]
    return boto3.client(
        "s3",
        aws_access_key_id     = s3_cfg["aws_access_key_id"],
        aws_secret_access_key = s3_cfg["aws_secret_access_key"],
        region_name           = s3_cfg["region"],
    )


def write_parquet_to_s3(s3, bucket, s3_key, df):
    """Write a DataFrame as Parquet directly to S3 — no temp files."""
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=s3_key, Body=buffer.getvalue())


def build_s3_key(bronze_prefix, table_name, batch_end, batch_ts):
    """
    Path: bronze/orders/year=2024/month=06/day=15/batch_20240615_080000.parquet
    Partitioned by date for efficient querying in Databricks.
    """
    short_name = table_name.replace("retailco_", "")
    return (
        f"{bronze_prefix}/{short_name}/"
        f"year={batch_end.year}/"
        f"month={batch_end.month:02d}/"
        f"day={batch_end.day:02d}/"
        f"batch_{batch_ts}.parquet"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg = load_config()
    s3_cfg = cfg["staging"]["s3"]

    # Capture batch_end once — all tables share the same window
    batch_end = datetime.now(timezone.utc).replace(tzinfo=None)
    batch_ts  = batch_end.strftime("%Y%m%d_%H%M%S")

    pg_conn, pg_cur = get_pg_connection(cfg)
    s3 = get_s3_client(cfg)
    bucket = s3_cfg["bucket"]
    bronze_prefix = s3_cfg["bronze_prefix"]

    # Step 1 — Read watermark
    last_watermark = read_watermark(pg_cur)
    window_start   = last_watermark - timedelta(minutes=OVERLAP_MINUTES)

    print(f"\nExtraction window:")
    print(f"  From : {window_start}  (watermark - {OVERLAP_MINUTES} min overlap)")
    print(f"  To   : {batch_end}")
    print()

    # Step 2 — Extract and write each table
    results = {}
    all_success = True

    for table in TABLES:
        print(f"Processing {table}...")
        try:
            df = extract_table(pg_cur, table, window_start, batch_end)

            if df.empty:
                print(f"  No changed records — skipping S3 write")
                results[table] = 0
                continue

            s3_key = build_s3_key(bronze_prefix, table, batch_end, batch_ts)
            write_parquet_to_s3(s3, bucket, s3_key, df)

            results[table] = len(df)
            print(f"  Extracted : {len(df)} rows")
            print(f"  Written   : s3://{bucket}/{s3_key}")

        except Exception as e:
            print(f"  FAILED: {e}")
            all_success = False
            break

    # Step 3 — Update watermark ONLY if all writes succeeded
    print()
    if all_success:
        update_watermark(pg_cur, batch_end)
    else:
        print("  Watermark NOT updated — one or more writes failed")
        print("  Next run will re-extract the same window safely")
        pg_conn.close()
        sys.exit(1)

    # Summary
    print()
    print("=" * 50)
    print("Bronze extraction complete")
    print("=" * 50)
    for table, count in results.items():
        print(f"  {table:<30} {count:>6} rows")
    print(f"  Total                          {sum(results.values()):>6} rows")
    print(f"  Batch timestamp : {batch_ts}")
    print(f"  New watermark   : {batch_end}")

    pg_conn.close()


if __name__ == "__main__":
    run()
