-- Notebook: 04_gold_facts
-- Layer: Gold
-- Purpose: Build two fact tables by joining Silver tables with Gold dimensions.
--   fact_orders      - grain: one row per order
--   fact_order_items - grain: one row per order line item
--
-- Star schema join keys:
--   fact_orders      -> dim_customer  via customer_id -> customer_key
--   fact_orders      -> dim_date      via DATE_FORMAT(created_at) -> date_key
--   fact_order_items -> dim_product   via product_id  -> product_key
--   fact_order_items -> dim_customer  via orders.customer_id
--   fact_order_items -> dim_date      via DATE_FORMAT(created_at)

USE CATALOG workspace;
USE SCHEMA customer360;

-- ── fact_orders ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gold_fact_orders (
  order_key      BIGINT    NOT NULL,
  order_id       BIGINT,
  customer_key   BIGINT,
  date_key       INT,
  status         STRING,
  total_amount   DOUBLE,
  item_count     BIGINT,
  region         STRING,
  created_at     TIMESTAMP,
  updated_at     TIMESTAMP,
  dw_inserted_at TIMESTAMP
) USING DELTA
COMMENT 'Fact table for orders. Grain: one row per order.';

MERGE INTO gold_fact_orders AS target
USING (
  SELECT
    o.order_id                                                   AS order_key,
    o.order_id,
    COALESCE(c.customer_key, -1)                                 AS customer_key,
    CAST(DATE_FORMAT(o.created_at, 'yyyyMMdd') AS INT)           AS date_key,
    o.status,
    o.total_amount,
    COALESCE(item_agg.item_count, 0)                             AS item_count,
    o.region,
    o.created_at,
    o.updated_at,
    current_timestamp()                                          AS dw_inserted_at
  FROM silver_orders o
  LEFT JOIN gold_dim_customer c       ON o.customer_id  = c.customer_id
  LEFT JOIN (
    SELECT order_id, COUNT(*) AS item_count
    FROM silver_order_items
    GROUP BY order_id
  ) item_agg ON o.order_id = item_agg.order_id
) AS source
ON target.order_key = source.order_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── fact_order_items ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gold_fact_order_items (
  item_key       BIGINT    NOT NULL,
  item_id        BIGINT,
  order_id       BIGINT,
  customer_key   BIGINT,
  product_key    BIGINT,
  date_key       INT,
  quantity       INT,
  unit_price     DOUBLE,
  line_total     DOUBLE,
  created_at     TIMESTAMP,
  dw_inserted_at TIMESTAMP
) USING DELTA
COMMENT 'Fact table for order line items. Grain: one row per item.';

MERGE INTO gold_fact_order_items AS target
USING (
  SELECT
    i.item_id                                                    AS item_key,
    i.item_id,
    i.order_id,
    COALESCE(c.customer_key, -1)                                 AS customer_key,
    COALESCE(p.product_key,  -1)                                 AS product_key,
    CAST(DATE_FORMAT(i.created_at, 'yyyyMMdd') AS INT)           AS date_key,
    i.quantity,
    i.unit_price,
    ROUND(i.quantity * i.unit_price, 2)                          AS line_total,
    i.created_at,
    current_timestamp()                                          AS dw_inserted_at
  FROM silver_order_items i
  LEFT JOIN silver_orders      o ON i.order_id   = o.order_id
  LEFT JOIN gold_dim_customer  c ON o.customer_id = c.customer_id
  LEFT JOIN gold_dim_product   p ON i.product_id  = p.product_id
) AS source
ON target.item_key = source.item_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;


-- ── Summary ───────────────────────────────────────────────────────────────────

SELECT
  'gold_fact_orders'      AS table_name, COUNT(*) AS row_count FROM gold_fact_orders
UNION ALL
SELECT 'gold_fact_order_items',            COUNT(*) FROM gold_fact_order_items;
