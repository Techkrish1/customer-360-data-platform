# Architecture Principles

Principles applied consistently across all problems in this series.

## 1. Idempotency First
Every pipeline must produce the same result if run twice for the same input window.
This means: upserts not inserts, watermarks not timestamps in filenames, MERGE not INSERT.

## 2. Separation of Extraction and Loading
Raw data always lands in a staging layer (ADLS/S3) before reaching the warehouse.
Reason: decouples failure domains. Extraction failure does not corrupt the warehouse.
Loading failure can retry from the staged file without hitting the source again.

## 3. Watermarks Are Owned by the Pipeline, Not the Tool
Watermark state must survive tool recreation, migration, and failure.
Store watermarks in a dedicated metadata table, not in tool-specific variables or memory.

## 4. Assumptions Are Explicit
Every pipeline documents its assumptions.
Silent assumptions become production incidents.

## 5. Synthetic Data Only
All experiments use synthetic or publicly available datasets.
No real customer data, company data, or confidential information in this repository.

## 6. Credibility Honesty
- `I implemented` = built and ran
- `I explored` = studied and understood
- `I designed` = conceptual only
