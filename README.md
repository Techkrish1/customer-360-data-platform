# Data Engineering Problems Portfolio

Real-world Data Engineering problems solved end-to-end.

Each problem follows the same structure:
1. **Business Problem** — what the business actually needs and why
2. **Architecture** — design decisions, trade-offs, alternatives
3. **CDI / CDIE Implementation** — Informatica Cloud approach
4. **PySpark Implementation** — explicit code-level engineering
5. **Experiments** — measured comparisons, not claimed improvements
6. **Interview Questions** — what interviewers probe at each decision point
7. **LinkedIn Posts** — one concept per post, discussion-worthy framing

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Source | PostgreSQL (Docker) |
| Raw / Bronze | ADLS Gen2 (Parquet / Delta) |
| Object Storage | AWS S3 |
| Transformation | Informatica CDI / CDIE, PySpark |
| Warehouse | Snowflake |
| Lakehouse | Microsoft Fabric |
| Orchestration | To be added |

---

## Problems

| # | Problem | Core Concept | Status |
|---|---------|-------------|--------|
| 01 | [Incremental Data Ingestion](problems/01-incremental-ingestion/README.md) | High-water mark, idempotency, watermark state | In Progress |

---

## Credibility Rules

- `I implemented` — built and ran myself
- `I explored` — studied and understood but not run in production
- `I designed` — conceptual design only

No real company data. No confidential architecture. Synthetic datasets only.

---

## Connect

LinkedIn: [Gokulakrishnan Venkatesan](https://www.linkedin.com/in/gokulakrishnan-venkatesan-93a3a8227)
