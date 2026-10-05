# Architecture — Problem 01: Incremental Ingestion

## Pipeline Overview

```
PostgreSQL (Source)
      |
      |  JDBC · WHERE updated_at > watermark - 15min
      |
      v
S3 Bronze  --  raw Parquet  --  immutable, exactly as extracted
      |
      |  PySpark on Databricks · clean · deduplicate · validate
      |
      v
S3 Silver  --  Delta Lake  --  trusted, clean, ACID
      |
      |  PySpark on Databricks · RFM · customer features · churn score
      |
      v
S3 Gold    --  Delta Lake  --  analytics-ready, aggregated
      |
      |  Databricks SQL Warehouse
      |
      v
Power BI Dashboard
```

Watermark metadata table lives in PostgreSQL.
Read at extraction time. Written only after confirmed Bronze write.

---

## Layer Contracts

| Layer | Job | Format | Written by | Read by |
|-------|-----|--------|-----------|---------|
| Bronze | Store exactly what was extracted | Parquet | Extractor | Silver job |
| Silver | Store clean, validated, trusted data | Delta Lake | Silver job | Gold job |
| Gold | Store analytics-ready aggregations | Delta Lake | Gold job | Power BI |

---

## S3 Path Structure

```
s3://gvenkatesan-c360/customer-360/
    bronze/
        orders/year=YYYY/month=MM/day=DD/batch_YYYYMMDD_HHMMSS.parquet
        customers/year=YYYY/month=MM/day=DD/batch_YYYYMMDD_HHMMSS.parquet
        order_items/year=YYYY/month=MM/day=DD/batch_YYYYMMDD_HHMMSS.parquet
    silver/
        orders/          (Delta table)
        customers/       (Delta table)
        order_items/     (Delta table)
    gold/
        customer_features/   (Delta table — RFM + churn score)
```

---

## Key Decisions

### Why Bronze / Silver / Gold?
Each layer is independently reprocessable. If Silver logic has a bug,
fix and reprocess from Bronze without touching PostgreSQL.
Trade-off: more storage and jobs. Acceptable — recovery value outweighs cost.

### Why Parquet for Bronze, Delta for Silver/Gold?
Bronze is append-only — Parquet is sufficient, simpler, faster.
Silver/Gold need MERGE (upsert), ACID, time travel, schema evolution — only Delta provides these.

### Why the watermark lives in PostgreSQL
Must survive pipeline recreation. Must be queryable and auditable.
Must be manually resettable for backfills. A database table satisfies all three.
CDI variables, S3 files, and in-memory state do not.

### Why a 15-minute overlap window
Protects against records committed just after query execution.
Overlap creates duplicates. Silver MERGE on primary key resolves them.

### Watermark update rule
Updated ONLY after confirmed successful S3 Bronze write.
Never before. Ensures safe re-runs on failure.

---

## Failure Recovery

| Failure point | Recovery |
|--------------|----------|
| Extraction fails | Watermark unchanged — re-extract same window |
| S3 Bronze write fails | Watermark unchanged — safe retry |
| Silver job fails | Bronze intact — reprocess from Bronze |
| Gold job fails | Silver intact — reprocess from Silver |

No failure requires re-hitting PostgreSQL more than once per window.
No failure produces duplicates in Gold.

---

## Scale Ceiling

| Volume | Approach |
|--------|----------|
| Current 20K rows | Single node, no partitioning |
| 500K rows/batch | Partition Bronze by date |
| 5M rows/batch | Parallel JDBC reads, multi-node cluster |
| 50M rows/batch | Watermark approach breaks — replace with CDC |

This architecture is designed to be replaced by CDC at scale, not to fight it.
