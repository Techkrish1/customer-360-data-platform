-- Notebook: 05_gold_mart
-- Layer: Gold Mart
-- Purpose: Build mart_customer_rfm — one row per customer with full RFM profile.
--          This is the single table Power BI connects to (no joins at query time).
--
-- RFM Scoring:
--   R (Recency)   - days since last order; lower = better = score 5
--   F (Frequency) - total order count;    higher = better = score 5
--   M (Monetary)  - total spend;          higher = better = score 5
--   Score 1-5 using NTILE(5) percentile bands
--
-- Segments (8):
--   Champions, Loyal Customers, Potential Loyalists, New Customers,
--   At Risk, Cannot Lose Them, Hibernating, Lost
--
-- Churn Risk:
--   HIGH   > 90 days since last order
--   MEDIUM 31-90 days
--   LOW    <= 30 days

USE CATALOG workspace;
USE SCHEMA customer360;

-- Rebuild mart as a complete snapshot (full overwrite on every run)
CREATE OR REPLACE TABLE gold_mart_rfm
USING DELTA
COMMENT 'Pre-aggregated RFM mart. One row per customer. Power BI connects here.'
AS
WITH customer_orders AS (
  SELECT
    c.customer_key,
    c.customer_id,
    c.name,
    c.email,
    c.region,
    c.tier,
    MIN(fo.created_at)                             AS first_order_date,
    MAX(fo.created_at)                             AS last_order_date,
    DATEDIFF(current_date(), MAX(fo.created_at))   AS recency_days,
    COUNT(fo.order_key)                            AS total_orders,
    ROUND(SUM(fo.total_amount), 2)                 AS total_spent,
    ROUND(AVG(fo.total_amount), 2)                 AS avg_order_value,
    SUM(fo.item_count)                             AS total_items
  FROM gold_fact_orders fo
  JOIN gold_dim_customer c ON fo.customer_key = c.customer_key
  GROUP BY
    c.customer_key, c.customer_id, c.name,
    c.email, c.region, c.tier
),
rfm_scored AS (
  SELECT *,
    -- Recency: low days = high score, so invert
    6 - NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,
    NTILE(5)     OVER (ORDER BY total_orders  ASC) AS f_score,
    NTILE(5)     OVER (ORDER BY total_spent   ASC) AS m_score
  FROM customer_orders
),
rfm_segmented AS (
  SELECT *,
    CONCAT(CAST(r_score AS STRING),
           CAST(f_score AS STRING),
           CAST(m_score AS STRING))                AS rfm_score,
    CASE
      WHEN r_score >= 4 AND f_score >= 4                      THEN 'Champions'
      WHEN r_score >= 4 AND f_score <= 2                      THEN 'New Customers'
      WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3     THEN 'Potential Loyalists'
      WHEN f_score >= 4                                       THEN 'Loyal Customers'
      WHEN r_score <= 2 AND f_score >= 3                      THEN 'At Risk'
      WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3     THEN 'Cannot Lose Them'
      WHEN r_score <= 2                                       THEN 'Lost'
      ELSE                                                         'Hibernating'
    END                                            AS rfm_segment,
    CASE
      WHEN recency_days > 90 THEN 'HIGH'
      WHEN recency_days > 30 THEN 'MEDIUM'
      ELSE                        'LOW'
    END                                            AS churn_risk,
    current_timestamp()                            AS pipeline_updated_at
  FROM rfm_scored
)
SELECT
  customer_key, customer_id, name, email, region, tier,
  first_order_date, last_order_date, recency_days,
  total_orders, total_spent, avg_order_value, total_items,
  r_score, f_score, m_score, rfm_score,
  rfm_segment, churn_risk,
  pipeline_updated_at
FROM rfm_segmented;


-- ── Validation checks ─────────────────────────────────────────────────────────

SELECT 'Total customers' AS metric, COUNT(*) AS value FROM gold_mart_rfm
UNION ALL
SELECT 'Avg recency days',      ROUND(AVG(recency_days), 1) FROM gold_mart_rfm
UNION ALL
SELECT 'HIGH churn risk count', COUNT(*) FROM gold_mart_rfm WHERE churn_risk = 'HIGH'
UNION ALL
SELECT 'Champions count',       COUNT(*) FROM gold_mart_rfm WHERE rfm_segment = 'Champions';

-- Segment distribution
SELECT rfm_segment, COUNT(*) AS customers,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM gold_mart_rfm
GROUP BY rfm_segment
ORDER BY customers DESC;
