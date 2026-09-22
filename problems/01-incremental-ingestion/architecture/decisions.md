# Architecture Decisions — Problem 01

## Decision Log

| Decision | Choice | Alternatives Considered | Reason |
|----------|--------|------------------------|--------|
| Change detection | Watermark (`updated_at`) | CDC (Debezium), DB triggers, full diff | Simplest for SQL sources with reliable timestamps |
| Staging layer | ADLS Gen2 (Parquet) | Direct to Snowflake, S3 | Decouples extraction from loading, enables reprocessing |
| File format | Parquet | CSV, JSON, ORC | Columnar, compressed, schema-preserving |
| Watermark storage | Metadata table in Snowflake | File in ADLS, CDI variable | Survives pipeline recreation, queryable, auditable |
| Load strategy | MERGE (upsert) | INSERT only, truncate-reload | Handles re-runs without duplicates |

## Trade-offs

- Watermark approach misses hard deletes — acceptable if source uses soft deletes
- Overlap window introduces duplicates at extraction — resolved by upsert at load
- ADLS staging adds latency vs direct load — enables failure recovery and reprocessing

## Scale Considerations

- At 50M rows: watermark query is fast with index on `updated_at`
- At 500M rows: consider partitioned tables, parallel extraction by region/date
- At CDC scale: replace watermark with Debezium + Kafka to capture all change types
