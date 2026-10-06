"""
Script 04: Silver Delta -> Gold Fact Tables

Builds two fact tables:
  fact_orders      - one row per order   (grain: order)
  fact_order_items - one row per item    (grain: line item)

What this script does:
  - Reads Silver Delta tables (orders, customers, order_items)
  - Reads Gold Dimension tables (dim_customer, dim_product, dim_date)
  - Joins to replace natural keys with dimension surrogate keys
  - Computes derived measures (line_total, item_count)
  - MERGEs into Gold Delta fact tables

Star schema join keys:
  fact_orders      -> dim_customer  (customer_id  -> customer_key)
  fact_orders      -> dim_date      (created_at   -> date_key)
  fact_order_items -> dim_product   (product_id   -> product_key)
  fact_order_items -> dim_customer  (via orders   -> customer_key)
  fact_order_items -> dim_date      (created_at   -> date_key)
"""
import yaml
import pandas as pd
import pyarrow as pa
from datetime import datetime, timezone
from pathlib import Path

from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

CONFIG_PATH = Path(__file__).parents[1] / "config" / "config.yaml"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_storage_options(s3_cfg):
    return {
        "AWS_ACCESS_KEY_ID"         : s3_cfg["aws_access_key_id"],
        "AWS_SECRET_ACCESS_KEY"     : s3_cfg["aws_secret_access_key"],
        "AWS_REGION"                : s3_cfg["region"],
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }


# ── Read Delta tables ─────────────────────────────────────────────────────────

def read_delta(path, opts):
    return DeltaTable(path, storage_options=opts).to_pandas()


# ── Write Gold fact tables ────────────────────────────────────────────────────

def write_gold_fact(df, gold_path, pk, opts):
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    try:
        dt = DeltaTable(gold_path, storage_options=opts)
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
        write_deltalake(gold_path, arrow_table,
                        storage_options=opts, mode="overwrite")
        print(f"  Gold action   : CREATE (first write)")


# ── fact_orders ───────────────────────────────────────────────────────────────

def build_fact_orders(silver_orders, silver_items, dim_customer, dim_date):
    """
    Joins:
      orders + dim_customer  -> customer_key
      orders + dim_date      -> date_key  (from created_at)
      orders + item counts   -> item_count (pre-aggregated measure)
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Pre-compute item count per order from Silver items
    item_counts = (silver_items
                   .groupby("order_id")
                   .size()
                   .reset_index(name="item_count"))

    # date_key: convert created_at to YYYYMMDD integer to match dim_date
    silver_orders = silver_orders.copy()
    silver_orders["date_key"] = (pd.to_datetime(silver_orders["created_at"])
                                   .dt.strftime("%Y%m%d")
                                   .astype(int))

    # Join customer surrogate key
    df = silver_orders.merge(
        dim_customer[["customer_id", "customer_key"]],
        on="customer_id", how="left"
    )

    # Join item count
    df = df.merge(item_counts, on="order_id", how="left")
    df["item_count"] = df["item_count"].fillna(0).astype(int)

    # Flag unresolved dimension keys (data quality indicator)
    unresolved = df["customer_key"].isna().sum()
    if unresolved:
        print(f"  WARNING: {unresolved} orders have no matching customer in dim_customer")

    fact = pd.DataFrame({
        "order_key"      : df["order_id"],           # surrogate = natural for now
        "order_id"       : df["order_id"],            # natural key kept for traceability
        "customer_key"   : df["customer_key"].fillna(-1).astype(int),
        "date_key"       : df["date_key"],
        "status"         : df["status"],
        "total_amount"   : df["total_amount"],
        "item_count"     : df["item_count"],
        "region"         : df["region"],
        "created_at"     : df["created_at"],
        "updated_at"     : df["updated_at"],
        "dw_inserted_at" : now,
    })

    return fact


# ── fact_order_items ──────────────────────────────────────────────────────────

def build_fact_order_items(silver_items, silver_orders, dim_customer, dim_product):
    """
    Joins:
      items + orders        -> customer_id (order_items has no customer_id directly)
      items + dim_customer  -> customer_key
      items + dim_product   -> product_key
      items                 -> date_key from created_at
      items                 -> line_total = quantity * unit_price (derived measure)
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Bring customer_id from orders into items
    order_customer = silver_orders[["order_id", "customer_id"]]
    df = silver_items.merge(order_customer, on="order_id", how="left")

    # Join surrogate keys
    df = df.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
    df = df.merge(dim_product[["product_id", "product_key"]],   on="product_id",  how="left")

    # date_key from created_at
    df["date_key"] = (pd.to_datetime(df["created_at"])
                        .dt.strftime("%Y%m%d")
                        .astype(int))

    # Derived measure
    df["line_total"] = (df["quantity"] * df["unit_price"]).round(2)

    unresolved_products = df["product_key"].isna().sum()
    if unresolved_products:
        print(f"  WARNING: {unresolved_products} items have no matching product in dim_product")

    fact = pd.DataFrame({
        "item_key"       : df["item_id"],
        "item_id"        : df["item_id"],
        "order_id"       : df["order_id"],
        "customer_key"   : df["customer_key"].fillna(-1).astype(int),
        "product_key"    : df["product_key"].fillna(-1).astype(int),
        "date_key"       : df["date_key"],
        "quantity"       : df["quantity"],
        "unit_price"     : df["unit_price"],
        "line_total"     : df["line_total"],
        "created_at"     : df["created_at"],
        "dw_inserted_at" : now,
    })

    return fact


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg    = load_config()
    s3_cfg = cfg["staging"]["s3"]
    bucket = s3_cfg["bucket"]
    opts   = get_storage_options(s3_cfg)
    base   = f"s3://{bucket}/customer-360"

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nGold facts started at {run_ts}\n")

    # Load Silver tables
    print("Loading Silver tables...")
    silver_orders   = read_delta(f"{base}/silver/orders",      opts)
    silver_customers = read_delta(f"{base}/silver/customers",  opts)
    silver_items    = read_delta(f"{base}/silver/order_items", opts)
    print(f"  silver.orders        : {len(silver_orders):>6} rows")
    print(f"  silver.customers     : {len(silver_customers):>6} rows")
    print(f"  silver.order_items   : {len(silver_items):>6} rows")
    print()

    # Load Gold dimension tables
    print("Loading Gold dimensions...")
    dim_customer = read_delta(f"{base}/gold/dim_customer", opts)
    dim_product  = read_delta(f"{base}/gold/dim_product",  opts)
    dim_date     = read_delta(f"{base}/gold/dim_date",     opts)
    print(f"  dim_customer         : {len(dim_customer):>6} rows")
    print(f"  dim_product          : {len(dim_product):>6} rows")
    print(f"  dim_date             : {len(dim_date):>6} rows")
    print()

    # Build and write fact_orders
    print("--- fact_orders ---")
    fact_orders = build_fact_orders(silver_orders, silver_items, dim_customer, dim_date)
    write_gold_fact(fact_orders, f"{base}/gold/fact_orders", "order_key", opts)
    print(f"  Rows written  : {len(fact_orders)}")
    print(f"  Written to    : {base}/gold/fact_orders")
    print()

    # Build and write fact_order_items
    print("--- fact_order_items ---")
    fact_items = build_fact_order_items(silver_items, silver_orders, dim_customer, dim_product)
    write_gold_fact(fact_items, f"{base}/gold/fact_order_items", "item_key", opts)
    print(f"  Rows written  : {len(fact_items)}")
    print(f"  Written to    : {base}/gold/fact_order_items")
    print()

    print("=" * 50)
    print("Gold facts complete — Star Schema ready")
    print("=" * 50)
    print(f"  fact_orders          : {len(fact_orders):>6} rows")
    print(f"  fact_order_items     : {len(fact_items):>6} rows")
    print()
    print("Gold layer tables:")
    print("  dim_customer, dim_product, dim_date")
    print("  fact_orders, fact_order_items")
    print("  -> mart_customer_rfm  (Script 05 — next)")


if __name__ == "__main__":
    run()
