-- Notebook: 03_gold_dimensions
-- Layer: Gold
-- Purpose: Build three dimension tables from Silver.
--   dim_customer  - SCD Type 1 (current state only; SCD Type 2 in Problem 03)
--   dim_product   - Synthetic product catalogue (no source table)
--   dim_date      - Pure calendar table generated with SEQUENCE

USE CATALOG workspace;
USE SCHEMA customer360;

-- ── dim_customer ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gold_dim_customer (
  customer_key   BIGINT    NOT NULL,
  customer_id    BIGINT,
  name           STRING,
  email          STRING,
  region         STRING,
  tier           STRING,
  is_current     BOOLEAN,
  effective_from TIMESTAMP,
  dw_inserted_at TIMESTAMP
) USING DELTA
COMMENT 'SCD Type 1 customer dimension. Grain: one row per customer_key.';

MERGE INTO gold_dim_customer AS target
USING (
  SELECT
    customer_id                    AS customer_key,
    customer_id,
    TRIM(name)                     AS name,
    LOWER(TRIM(email))             AS email,
    region,
    tier,
    TRUE                           AS is_current,
    created_at                     AS effective_from,
    current_timestamp()            AS dw_inserted_at
  FROM silver_customers
) AS source
ON target.customer_key = source.customer_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── dim_product ───────────────────────────────────────────────────────────────
-- No product source table exists. Generated synthetically from product_id range (1-200).

CREATE TABLE IF NOT EXISTS gold_dim_product
USING DELTA
COMMENT 'Synthetic product dimension. 200 rows covering product_id 1-200.'
AS
WITH products AS (
  SELECT
    pid AS product_key,
    pid AS product_id,
    CASE
      WHEN pid BETWEEN 1   AND 50  THEN 'Electronics'
      WHEN pid BETWEEN 51  AND 100 THEN 'Clothing'
      WHEN pid BETWEEN 101 AND 150 THEN 'Home & Kitchen'
      ELSE                              'Books & Media'
    END AS category,
    CASE
      WHEN pid BETWEEN 1   AND 50  THEN CONCAT('Electronic Product ', pid)
      WHEN pid BETWEEN 51  AND 100 THEN CONCAT('Clothing Item ',      pid)
      WHEN pid BETWEEN 101 AND 150 THEN CONCAT('Kitchen Product ',    pid)
      ELSE                              CONCAT('Book or Media ',       pid)
    END AS product_name,
    TRUE AS is_active
  FROM (SELECT EXPLODE(SEQUENCE(1, 200)) AS pid)
)
SELECT *, current_timestamp() AS dw_inserted_at FROM products;


-- ── dim_date ──────────────────────────────────────────────────────────────────
-- Pure calendar table. Covers 2024-01-01 to 2027-12-31 (1461 rows).

CREATE TABLE IF NOT EXISTS gold_dim_date
USING DELTA
COMMENT 'Calendar dimension. 1461 days from 2024-01-01 to 2027-12-31.'
AS
SELECT
  CAST(DATE_FORMAT(d, 'yyyyMMdd') AS INT)  AS date_key,
  d                                         AS full_date,
  DAY(d)                                    AS day_of_month,
  DAYOFWEEK(d)                              AS day_of_week,
  DATE_FORMAT(d, 'EEEE')                    AS day_name,
  WEEKOFYEAR(d)                             AS week_of_year,
  MONTH(d)                                  AS month_number,
  DATE_FORMAT(d, 'MMMM')                    AS month_name,
  QUARTER(d)                                AS quarter,
  YEAR(d)                                   AS year,
  DAYOFWEEK(d) IN (1, 7)                    AS is_weekend,
  DAYOFWEEK(d) NOT IN (1, 7)               AS is_weekday
FROM (SELECT EXPLODE(SEQUENCE(DATE('2024-01-01'), DATE('2027-12-31'), INTERVAL 1 DAY)) AS d);


-- ── Summary ───────────────────────────────────────────────────────────────────

SELECT
  'gold_dim_customer' AS table_name, COUNT(*) AS row_count FROM gold_dim_customer
UNION ALL
SELECT 'gold_dim_product',             COUNT(*) FROM gold_dim_product
UNION ALL
SELECT 'gold_dim_date',                COUNT(*) FROM gold_dim_date;
