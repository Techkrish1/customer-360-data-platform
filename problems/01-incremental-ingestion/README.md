# Problem 01 — Incremental Data Ingestion

## Business Problem

RetailCo runs its order management system on PostgreSQL. The analytics team needs order data
in Snowflake for reporting. Their current pipeline does a full table reload every night.

**The problem:** The orders table has grown to 50M rows. The nightly load takes 4 hours,
puts read pressure on the production database, and data is stale by up to 23 hours.

**The requirement:** Extract only new and changed records since the last successful run.
Stage in ADLS. Load into Snowflake. Run every 2 hours. Data freshness SLA: 2 hours 15 minutes.

---

## Source Schema

```sql
orders (
    order_id        BIGINT PRIMARY KEY,
    customer_id     BIGINT,
    status          VARCHAR(20),
    total_amount    NUMERIC(12,2),
    region          VARCHAR(50),
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
)

order_items (
    item_id         BIGINT PRIMARY KEY,
    order_id        BIGINT,
    product_id      BIGINT,
    quantity        INT,
    unit_price      NUMERIC(10,2),
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
)

customers (
    customer_id     BIGINT PRIMARY KEY,
    email           VARCHAR(255),
    name            VARCHAR(255),
    region          VARCHAR(50),
    tier            VARCHAR(20),
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
)
```

---

## Assumptions

| Assumption | Why It Matters |
|-----------|---------------|
| `updated_at` is populated and reliable | If the application skips this column, changes are missed silently |
| Records are soft-deleted only | Hard DELETEs produce no `updated_at` change — invisible to watermark logic |
| Timestamps are in UTC | Clock skew and DST transitions can drop records outside the extraction window |
| `updated_at` has a database index | Without it, every incremental run is a full table scan |
| No backdated `updated_at` values | Late-arriving data with past timestamps will not be captured |

---

## Engineering Questions

1. What constitutes a "change" — inserts only, updates, deletes?
2. Where does the watermark live, and who owns it if the pipeline is recreated?
3. What is the overlap window to handle records committed just after the last run?
4. What happens if the pipeline fails after extraction but before the Snowflake load?
5. How do you handle late-arriving data with a backdated `updated_at`?
6. What does "2-hour freshness SLA" actually mean measured at the Snowflake end?

---

## Contents

| Folder | Contents |
|--------|---------|
| [architecture/](architecture/) | Design diagram, decisions, trade-offs |
| [cdi/](cdi/) | Informatica CDI/CDIE approach and screenshots |
| [pyspark/](pyspark/) | PySpark implementation |
| [sql/](sql/) | Watermark queries, upsert logic |
| [tests/](tests/) | Pipeline tests |
| [data/](data/) | Synthetic sample data only |
| [linkedin/](linkedin/) | LinkedIn post drafts |
