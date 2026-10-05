"""
Script 05: Gold Star Schema -> mart_customer_rfm

Builds one analytics-ready mart table for Power BI:
  mart_customer_rfm - one row per customer with full RFM profile

What this computes per customer:
  Recency   - days since their last order
  Frequency - total number of orders placed
  Monetary  - total amount spent

  R/F/M Scores  - each dimension scored 1-5 (5 = best)
  RFM Segment   - Champions / Loyal / Potential / At Risk / Lost / New
  Churn Risk    - HIGH / MEDIUM / LOW  (rule-based, not ML)

Why a mart instead of querying fact + dim directly?
  - Power BI performs better on a single pre-aggregated table
  - No joins at query time = faster dashboard load
  - Business users get clean column names without SQL knowledge
  - This pattern is standard in any customer analytics platform
"""
import yaml
import pandas as pd
import pyarrow as pa
from datetime import datetime, timezone
from pathlib import Path

from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"


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


def read_delta(path, opts):
    return DeltaTable(path, storage_options=opts).to_pandas()


# ── RFM Scoring ───────────────────────────────────────────────────────────────

def score_rfm(df):
    """
    Score each RFM dimension 1-5 using percentile ranking.
    5 = best in each dimension.

    Recency  : lower days = better = higher score
    Frequency: more orders = better = higher score
    Monetary : more spend  = better = higher score
    """
    # Use rank(pct=True) to get 0-1 percentile then scale to 1-5
    df["r_score"] = (
        df["recency_days"]
        .rank(pct=True, ascending=False)   # ascending=False: low recency days = high rank
        .mul(4).add(1).clip(1, 5).round().astype(int)
    )
    df["f_score"] = (
        df["total_orders"]
        .rank(pct=True, ascending=True)
        .mul(4).add(1).clip(1, 5).round().astype(int)
    )
    df["m_score"] = (
        df["total_spent"]
        .rank(pct=True, ascending=True)
        .mul(4).add(1).clip(1, 5).round().astype(int)
    )
    df["rfm_score"] = (
        df["r_score"].astype(str)
        + df["f_score"].astype(str)
        + df["m_score"].astype(str)
    )
    return df


def assign_segment(row):
    """
    Rule-based RFM segmentation.
    Used by Power BI to colour-code customers in the dashboard.
    """
    r, f, m = row["r_score"], row["f_score"], row["m_score"]

    if r >= 4 and f >= 4:
        return "Champions"
    elif r >= 4 and f <= 2:
        return "New Customers"
    elif r >= 3 and f >= 3 and m >= 3:
        return "Potential Loyalists"
    elif f >= 4:
        return "Loyal Customers"
    elif r <= 2 and f >= 3:
        return "At Risk"
    elif r <= 2 and f <= 2 and m >= 3:
        return "Cannot Lose Them"
    elif r <= 2:
        return "Lost"
    else:
        return "Hibernating"


def assign_churn_risk(recency_days):
    """
    Rule-based churn risk.
    Replaces an ML model for this project — same business value, explainable.
    """
    if recency_days > 90:
        return "HIGH"
    elif recency_days > 30:
        return "MEDIUM"
    else:
        return "LOW"


# ── Build mart ────────────────────────────────────────────────────────────────

def build_mart(fact_orders, dim_customer):
    now            = datetime.now(timezone.utc).replace(tzinfo=None)
    reference_date = pd.Timestamp.now()

    # Aggregate fact_orders per customer
    agg = (fact_orders
           .groupby("customer_key")
           .agg(
               total_orders     = ("order_key",    "count"),
               total_spent      = ("total_amount", "sum"),
               total_items      = ("item_count",   "sum"),
               first_order_date = ("created_at",   "min"),
               last_order_date  = ("created_at",   "max"),
           )
           .reset_index())

    agg["total_spent"]      = agg["total_spent"].round(2)
    agg["avg_order_value"]  = (agg["total_spent"] / agg["total_orders"]).round(2)
    agg["recency_days"]     = (
        (reference_date - pd.to_datetime(agg["last_order_date"]))
        .dt.days
    )

    # Join customer attributes from dim_customer
    mart = agg.merge(
        dim_customer[["customer_key", "customer_id", "name",
                      "email", "region", "tier"]],
        on="customer_key", how="left"
    )

    # Score and segment
    mart = score_rfm(mart)
    mart["rfm_segment"]  = mart.apply(assign_segment, axis=1)
    mart["churn_risk"]   = mart["recency_days"].apply(assign_churn_risk)
    mart["pipeline_updated_at"] = now

    # Final column order — matches Power BI expected schema
    mart = mart[[
        "customer_key", "customer_id", "name", "email",
        "region", "tier",
        "first_order_date", "last_order_date", "recency_days",
        "total_orders", "total_spent", "avg_order_value", "total_items",
        "r_score", "f_score", "m_score", "rfm_score",
        "rfm_segment", "churn_risk",
        "pipeline_updated_at",
    ]]

    return mart


# ── Write mart ────────────────────────────────────────────────────────────────

def write_mart(df, path, opts):
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    try:
        dt = DeltaTable(path, storage_options=opts)
        (dt.merge(
            source       = arrow_table,
            predicate    = "target.customer_key = source.customer_key",
            source_alias = "source",
            target_alias = "target",
         )
         .when_matched_update_all()
         .when_not_matched_insert_all()
         .execute())
        print(f"  Mart action   : MERGE into existing table")
    except TableNotFoundError:
        write_deltalake(path, arrow_table,
                        storage_options=opts, mode="overwrite")
        print(f"  Mart action   : CREATE (first write)")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    cfg    = load_config()
    s3_cfg = cfg["staging"]["s3"]
    bucket = s3_cfg["bucket"]
    opts   = get_storage_options(s3_cfg)
    base   = f"s3://{bucket}/customer-360"

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nGold mart started at {run_ts}\n")

    print("Loading Gold tables...")
    fact_orders  = read_delta(f"{base}/gold/fact_orders",   opts)
    dim_customer = read_delta(f"{base}/gold/dim_customer",  opts)
    print(f"  fact_orders   : {len(fact_orders):>6} rows")
    print(f"  dim_customer  : {len(dim_customer):>6} rows")
    print()

    print("--- mart_customer_rfm ---")
    mart = build_mart(fact_orders, dim_customer)
    write_mart(mart, f"{base}/gold/mart_customer_rfm", opts)
    print(f"  Rows written  : {len(mart)}")
    print(f"  Written to    : {base}/gold/mart_customer_rfm")
    print()

    # Segment distribution — sanity check
    print("Segment distribution:")
    dist = mart["rfm_segment"].value_counts()
    for seg, count in dist.items():
        bar = "#" * int(count / len(mart) * 30)
        print(f"  {seg:<25} {count:>4}  {bar}")

    print()
    print("Churn risk distribution:")
    churn = mart["churn_risk"].value_counts()
    for risk, count in churn.items():
        print(f"  {risk:<10} {count:>4} customers")

    print()
    print("=" * 50)
    print("mart_customer_rfm complete — ready for Power BI")
    print("=" * 50)
    print(f"  Customers     : {len(mart)}")
    print(f"  Columns       : {len(mart.columns)}")


if __name__ == "__main__":
    run()
