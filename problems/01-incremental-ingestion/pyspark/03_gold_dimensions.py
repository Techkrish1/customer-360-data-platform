"""
Script 03: Silver Delta -> Gold Dimension Tables

Builds three dimension tables:
  dim_customer  - customer attributes  (SCD Type 1 — upgraded to Type 2 in Problem 03)
  dim_product   - product catalogue    (synthetic — no product source table exists)
  dim_date      - calendar table       (fully generated, no source required)

Why dimensions before facts?
  Fact tables reference dimension keys.
  Dimensions must exist and be populated first.

SCD Type 1 note:
  dim_customer stores current state only — MERGE overwrites changed attributes.
  History tracking (SCD Type 2) is Problem 03 in this series.
"""
import random
import yaml
import pandas as pd
import pyarrow as pa
from datetime import datetime, timezone
from pathlib import Path

from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"

random.seed(99)

PRODUCT_CATALOGUE = {
    range(1,   51): ("Electronics",   ["Laptop", "Smartphone", "Tablet", "Headphones", "Camera", "Charger", "Monitor"]),
    range(51, 101): ("Clothing",      ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Cap", "Hoodie", "Dress"]),
    range(101,151): ("Home & Kitchen",["Blender", "Toaster", "Coffee Maker", "Pan Set", "Knife Block", "Air Fryer"]),
    range(151,201): ("Books & Media", ["Novel", "Textbook", "Graphic Novel", "Magazine", "Audiobook", "Game"]),
}


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def storage_options(s3_cfg):
    return {
        "AWS_ACCESS_KEY_ID"         : s3_cfg["aws_access_key_id"],
        "AWS_SECRET_ACCESS_KEY"     : s3_cfg["aws_secret_access_key"],
        "AWS_REGION"                : s3_cfg["region"],
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }


# ── Read Silver ───────────────────────────────────────────────────────────────

def read_silver(s3_path, opts):
    dt = DeltaTable(s3_path, storage_options=opts)
    return dt.to_pandas()


# ── Write Gold Delta ──────────────────────────────────────────────────────────

def write_gold(df, gold_s3_path, pk, opts):
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    try:
        dt = DeltaTable(gold_s3_path, storage_options=opts)
        (dt.merge(
            source       = arrow_table,
            predicate    = f"target.{pk} = source.{pk}",
            source_alias = "source",
            target_alias = "target",
         )
         .when_matched_update_all()
         .when_not_matched_insert_all()
         .execute())
        print(f"  Gold action   : MERGE into existing table")
    except TableNotFoundError:
        write_deltalake(gold_s3_path, arrow_table,
                        storage_options=opts, mode="overwrite")
        print(f"  Gold action   : CREATE (first write)")


# ── dim_customer ──────────────────────────────────────────────────────────────

def build_dim_customer(silver_customers_path, opts):
    """
    SCD Type 1 — current state only.
    customer_key = customer_id (natural key serves as surrogate for now).
    Upgraded to a proper surrogate key with history in Problem 03.
    """
    df = read_silver(silver_customers_path, opts)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    dim = pd.DataFrame({
        "customer_key"   : df["customer_id"],
        "customer_id"    : df["customer_id"],
        "name"           : df["name"].str.strip(),
        "email"          : df["email"].str.strip().str.lower(),
        "region"         : df["region"],
        "tier"           : df["tier"],
        "is_current"     : True,
        "effective_from" : df["created_at"],
        "dw_inserted_at" : now,
    })

    print(f"  Rows built    : {len(dim)}")
    return dim


# ── dim_product ───────────────────────────────────────────────────────────────

def build_dim_product():
    """
    No product source table exists in PostgreSQL.
    Generated synthetically using the product_id range from order_items (1–200).
    """
    rows = []
    for pid in range(1, 201):
        for id_range, (category, names) in PRODUCT_CATALOGUE.items():
            if pid in id_range:
                rows.append({
                    "product_key"    : pid,
                    "product_id"     : pid,
                    "product_name"   : f"{random.choice(names)} {pid}",
                    "category"       : category,
                    "is_active"      : True,
                    "dw_inserted_at" : datetime.now(timezone.utc).replace(tzinfo=None),
                })
                break

    df = pd.DataFrame(rows)
    print(f"  Rows built    : {len(df)}")
    return df


# ── dim_date ──────────────────────────────────────────────────────────────────

def build_dim_date(start="2024-01-01", end="2027-12-31"):
    """
    Pure calendar table — generated entirely in code, no source needed.
    Covers full date range of the project data plus future years for Power BI.
    """
    dates = pd.date_range(start=start, end=end, freq="D")

    df = pd.DataFrame({
        "date_key"     : dates.strftime("%Y%m%d").astype(int),
        "full_date"    : pd.to_datetime(dates.date),
        "day_of_month" : dates.day,
        "day_of_week"  : dates.dayofweek + 1,          # 1=Monday … 7=Sunday
        "day_name"     : dates.strftime("%A"),
        "week_of_year" : dates.isocalendar().week.astype(int).values,
        "month_number" : dates.month,
        "month_name"   : dates.strftime("%B"),
        "quarter"      : dates.quarter,
        "year"         : dates.year,
        "is_weekend"   : (dates.dayofweek >= 5),
        "is_weekday"   : (dates.dayofweek < 5),
    })

    print(f"  Rows built    : {len(df)}  ({start} to {end})")
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg     = load_config()
    s3_cfg  = cfg["staging"]["s3"]
    bucket  = s3_cfg["bucket"]
    opts    = storage_options(s3_cfg)
    base    = f"s3://{bucket}/customer-360"

    run_ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nGold dimensions started at {run_ts}\n")

    # ── dim_customer
    print("--- dim_customer ---")
    dim_customer = build_dim_customer(f"{base}/silver/customers", opts)
    write_gold(dim_customer, f"{base}/gold/dim_customer", "customer_key", opts)
    print(f"  Written to    : {base}/gold/dim_customer")
    print()

    # ── dim_product
    print("--- dim_product ---")
    dim_product = build_dim_product()
    write_gold(dim_product, f"{base}/gold/dim_product", "product_key", opts)
    print(f"  Written to    : {base}/gold/dim_product")
    print()

    # ── dim_date
    print("--- dim_date ---")
    dim_date = build_dim_date()
    write_gold(dim_date, f"{base}/gold/dim_date", "date_key", opts)
    print(f"  Written to    : {base}/gold/dim_date")
    print()

    print("=" * 50)
    print("Gold dimensions complete")
    print("=" * 50)
    print(f"  dim_customer  : {len(dim_customer):>6} rows")
    print(f"  dim_product   : {len(dim_product):>6} rows")
    print(f"  dim_date      : {len(dim_date):>6} rows")


if __name__ == "__main__":
    run()
