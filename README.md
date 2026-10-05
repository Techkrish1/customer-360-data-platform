# Customer 360 Data Platform

An end-to-end Data Engineering platform that ingests, transforms, and delivers
customer behavioural data for churn risk analysis and segmentation.

Built to demonstrate production-grade Data Engineering thinking across:
architecture decisions, incremental pipelines, data quality, distributed processing,
and analytics-ready data delivery.

---

## What This Project Covers

Each problem in this series follows the same progression:

| Step | What |
|------|------|
| Business Problem | The real requirement, assumptions, and what a DE must think about first |
| Architecture | Design decisions, trade-offs, alternatives, and scale considerations |
| CDI / CDIE | Informatica implementation — what the platform abstracts and where it fits |
| PySpark | Code-level implementation — what the engineer must own explicitly |
| Experiments | Measured comparisons on real data — not claimed improvements |
| Interview Q&A | What interviewers probe at every decision point |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Source | PostgreSQL 14 |
| Raw / Bronze | S3 — Parquet |
| Silver / Gold | S3 — Delta Lake |
| Transformation | Informatica CDI / CDIE · PySpark |
| Lakehouse | Databricks |
| Visualisation | Power BI |

---

## Problems

| # | Problem | Core Engineering Concepts | Status |
|---|---------|--------------------------|--------|
| 01 | [Incremental Customer Data Ingestion](problems/01-incremental-ingestion/README.md) | High-water mark · Idempotency · Watermark state · Failure recovery | In Progress |
| 02 | Customer 360 Pipeline | Joins · Aggregations · RFM features · Late-arriving data | Planned |
| 03 | SCD Type 2 — Customer History | Slowly changing dimensions · History tracking · Upserts | Planned |
| 04 | Data Quality Framework | Expectations · Dead letters · Schema evolution | Planned |
| 05 | Spark Performance & Optimisation | Partitioning · Skew · Shuffle · Joins at scale | Planned |
| 06 | CDC Pipeline | Change data capture · Real-time vs near-real-time | Planned |
| 07 | Failure & Recovery | Retry logic · Backfill · Exactly-once semantics | Planned |
| 08 | Power BI — Customer Churn Dashboard | Analytics-ready data · RFM segmentation · Churn risk scoring | Planned |

---

## Architecture Principles

- **Idempotency first** — every pipeline produces the same result if run twice
- **Separate extraction from loading** — staging layer decouples failure domains
- **Watermarks are owned by the pipeline, not the tool** — persisted in metadata, not in-memory
- **Assumptions are explicit** — silent assumptions become production incidents
- **Cost is a first-class concern** — every architecture decision considers compute and storage cost

---

## Credibility

- `I implemented` — built and ran myself
- `I explored` — studied and understood, not run in production
- `I designed` — conceptual design only

No real company data. No confidential architecture. Synthetic datasets only.

---

## Connect

LinkedIn: [Gokulakrishnan Venkatesan](https://www.linkedin.com/in/gokulakrishnan-venkatesan-93a3a8227)
