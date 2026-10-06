-- Notebook: 02_silver_transform
-- Layer: Silver
-- Purpose: Deduplicate Bronze, validate business rules, MERGE into Silver Delta tables.
--
-- Rules applied:
--   orders      - positive total_amount, valid status, deduplicate on order_id (latest updated_at)
--   customers   - non-null email, valid tier, deduplicate on customer_id
--   order_items - positive quantity and unit_price, deduplicate on item_id

USE CATALOG workspace;
USE SCHEMA customer360;

-- ── Create Silver tables (first run only) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS silver_orders (
  order_id      BIGINT   NOT NULL,
  customer_id   BIGINT,
  status        STRING,
  total_amount  DOUBLE,
  region        STRING,
  created_at    TIMESTAMP,
  updated_at    TIMESTAMP
) USING DELTA
COMMENT 'Validated, deduplicated orders. Grain: one row per order_id.';

CREATE TABLE IF NOT EXISTS silver_customers (
  customer_id  BIGINT    NOT NULL,
  email        STRING,
  name         STRING,
  region       STRING,
  tier         STRING,
  created_at   TIMESTAMP,
  updated_at   TIMESTAMP
) USING DELTA
COMMENT 'Validated customer master. Grain: one row per customer_id.';

CREATE TABLE IF NOT EXISTS silver_order_items (
  item_id     BIGINT    NOT NULL,
  order_id    BIGINT,
  product_id  BIGINT,
  quantity    INT,
  unit_price  DOUBLE,
  created_at  TIMESTAMP,
  updated_at  TIMESTAMP
) USING DELTA
COMMENT 'Validated order line items. Grain: one row per item_id.';


-- ── MERGE Bronze → Silver: orders ─────────────────────────────────────────────

MERGE INTO silver_orders AS target
USING (
  SELECT order_id, customer_id, status, total_amount, region, created_at, updated_at
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rn
    FROM bronze_orders
    WHERE order_id    IS NOT NULL
      AND total_amount > 0
      AND status IN ('pending','confirmed','shipped','delivered','cancelled')
  )
  WHERE rn = 1
) AS source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── MERGE Bronze → Silver: customers ─────────────────────────────────────────

MERGE INTO silver_customers AS target
USING (
  SELECT customer_id, email, name, region, tier, created_at, updated_at
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) AS rn
    FROM bronze_customers
    WHERE customer_id IS NOT NULL
      AND email       IS NOT NULL
      AND tier IN ('standard','premium','enterprise')
  )
  WHERE rn = 1
) AS source
ON target.customer_id = source.customer_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── MERGE Bronze → Silver: order_items ───────────────────────────────────────

MERGE INTO silver_order_items AS target
USING (
  SELECT item_id, order_id, product_id, quantity, unit_price, created_at, updated_at
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY updated_at DESC) AS rn
    FROM bronze_order_items
    WHERE item_id   IS NOT NULL
      AND quantity  > 0
      AND unit_price > 0
  )
  WHERE rn = 1
) AS source
ON target.item_id = source.item_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── Summary ───────────────────────────────────────────────────────────────────

SELECT
  'silver_orders'      AS table_name, COUNT(*) AS row_count FROM silver_orders
UNION ALL
SELECT 'silver_customers',              COUNT(*) FROM silver_customers
UNION ALL
SELECT 'silver_order_items',            COUNT(*) FROM silver_order_items;
