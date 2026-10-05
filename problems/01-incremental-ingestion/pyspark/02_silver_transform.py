"""
Script 02: S3 Bronze Parquet -> S3 Silver Delta Lake

Flow per table:
  1. Read all Bronze Parquet files from S3
  2. Deduplicate — one row per primary key, latest updated_at wins
  3. Validate — drop null PKs, enforce business rules, log bad rows
  4. MERGE into Silver Delta table (INSERT new rows, UPDATE changed rows)

Why Delta for Silver and not Parquet?
  - MERGE requires ACID — Parquet has no transaction support
  - Overlap window in extraction creates duplicates — MERGE resolves them
  - Time travel lets us query Silver as it was at any point in the past
  - Schema evolution handles new source columns gracefully
"""
import io
import sys
import yaml
import boto3
import pandas as pd
import pyarrow as pa
from datetime import datetime, timezone
from pathlib import Path

from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"

# ── Table configuration ───────────────────────────────────────────────────────

TABLES = {
    "orders": {
        "pk":     "order_id",
        "bronze": "customer-360/bronze/orders/",
        "silver": "customer-360/silver/orders",
        "rules": {
            "drop_null_pk":        lambda df: df.dropna(subset=["order_id"]),
            "positive_amount":     lambda df: df[df["total_amount"] > 0],
            "valid_status":        lambda df: df[df["status"].isin(
                                       ["pending","confirmed","shipped","delivered","cancelled"])],
        }
    },
    "customers": {
        "pk":     "customer_id",
        "bronze": "customer-360/bronze/customers/",
        "silver": "customer-360/silver/customers",
        "rules": {
            "drop_null_pk":        lambda df: df.dropna(subset=["customer_id"]),
            "drop_null_email":     lambda df: df.dropna(subset=["email"]),
            "valid_tier":          lambda df: df[df["tier"].isin(
                                       ["standard","premium","enterprise"])],
        }
    },
    "order_items": {
        "pk":     "item_id",
        "bronze": "customer-360/bronze/order_items/",
        "silver": "customer-360/silver/order_items",
        "rules": {
            "drop_null_pk":        lambda df: df.dropna(subset=["item_id"]),
            "positive_quantity":   lambda df: df[df["quantity"] > 0],
            "positive_price":      lambda df: df[df["unit_price"] > 0],
        }
    },
}


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── Read Bronze from S3 ───────────────────────────────────────────────────────

def read_bronze(bucket, bronze_prefix, s3_client):
    """Read all Parquet files under the bronze prefix into one DataFrame."""
    resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=bronze_prefix)
    files = [
        obj["Key"] for obj in resp.get("Contents", [])
        if obj["Key"].endswith(".parquet")
    ]

    if not files:
        return pd.DataFrame()

    frames = []
    for key in files:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        frames.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))

    df = pd.concat(frames, ignore_index=True)
    print(f"  Bronze files read  : {len(files)}")
    print(f"  Rows before dedup  : {len(df)}")
    return df


# ── Deduplicate ───────────────────────────────────────────────────────────────

def deduplicate(df, pk):
    """Keep one row per primary key — the row with the latest updated_at."""
    before = len(df)
    df = (df
          .sort_values("updated_at", ascending=False)
          .drop_duplicates(subset=[pk])
          .reset_index(drop=True))
    dropped = before - len(df)
    if dropped:
        print(f"  Duplicates removed : {dropped}")
    return df


# ── Validate ──────────────────────────────────────────────────────────────────

def validate(df, rules, table_name):
    """Apply validation rules. Log and drop rows that fail."""
    total_dropped = 0
    for rule_name, rule_fn in rules.items():
        before = len(df)
        df = rule_fn(df).reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            print(f"  Rule [{rule_name}] dropped : {dropped} rows")
            total_dropped += dropped

    if total_dropped:
        print(f"  Total invalid rows : {total_dropped} (review source quality)")
    else:
        print(f"  Validation         : all rows passed")
    return df


# ── MERGE into Silver Delta ───────────────────────────────────────────────────

def merge_to_silver(df, silver_s3_path, pk, storage_options):
    """
    MERGE strategy:
      - If row with same PK exists in Silver: UPDATE all columns
      - If row is new: INSERT

    This resolves duplicates from the Bronze overlap window.
    Running this script twice produces the same Silver result — idempotent.
    """
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)

    try:
        dt = DeltaTable(silver_s3_path, storage_options=storage_options)

        (dt.merge(
            source        = arrow_table,
            predicate     = f"target.{pk} = source.{pk}",
            source_alias  = "source",
            target_alias  = "target"
         )
         .when_matched_update_all()
         .when_not_matched_insert_all()
         .execute())

        print(f"  Silver action      : MERGE (table exists)")

    except TableNotFoundError:
        write_deltalake(
            silver_s3_path,
            arrow_table,
            storage_options = storage_options,
            mode            = "overwrite",
        )
        print(f"  Silver action      : CREATE (first write)")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg     = load_config()
    s3_cfg  = cfg["staging"]["s3"]
    bucket  = s3_cfg["bucket"]

    storage_options = {
        "AWS_ACCESS_KEY_ID"        : s3_cfg["aws_access_key_id"],
        "AWS_SECRET_ACCESS_KEY"    : s3_cfg["aws_secret_access_key"],
        "AWS_REGION"               : s3_cfg["region"],
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }

    s3_client = boto3.client(
        "s3",
        aws_access_key_id     = s3_cfg["aws_access_key_id"],
        aws_secret_access_key = s3_cfg["aws_secret_access_key"],
        region_name           = s3_cfg["region"],
    )

    run_ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    summary = {}

    print(f"\nSilver transform started at {run_ts}\n")

    for table_name, table_cfg in TABLES.items():
        print(f"--- {table_name} ---")

        # Step 1 — Read Bronze
        df = read_bronze(bucket, table_cfg["bronze"], s3_client)

        if df.empty:
            print(f"  No Bronze data found — skipping")
            summary[table_name] = 0
            print()
            continue

        # Step 2 — Deduplicate
        df = deduplicate(df, table_cfg["pk"])

        # Step 3 — Validate
        df = validate(df, table_cfg["rules"], table_name)

        if df.empty:
            print(f"  All rows failed validation — skipping Silver write")
            summary[table_name] = 0
            print()
            continue

        # Step 4 — Merge into Silver Delta
        silver_path = f"s3://{bucket}/{table_cfg['silver']}"
        merge_to_silver(df, silver_path, table_cfg["pk"], storage_options)

        summary[table_name] = len(df)
        print(f"  Rows written       : {len(df)}")
        print()

    # Summary
    print("=" * 50)
    print("Silver transform complete")
    print("=" * 50)
    for table, count in summary.items():
        print(f"  {table:<20} {count:>6} rows in Silver")
    print(f"  Total              {sum(summary.values()):>6} rows")


if __name__ == "__main__":
    run()
