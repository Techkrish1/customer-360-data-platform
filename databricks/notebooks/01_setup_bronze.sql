-- Notebook: 01_setup_bronze
-- Layer: Bronze
-- Purpose: Register Bronze external Parquet tables pointing to the Unity Catalog Volume.
--          Bronze is append-only raw data. Never modified after landing.

USE CATALOG workspace;
USE SCHEMA customer360;

-- Bronze tables read directly from the Volume (uploaded by 01_extract_bronze.py via upload_to_volume.py)
CREATE TABLE IF NOT EXISTS bronze_orders
USING PARQUET
OPTIONS (path "/Volumes/workspace/customer360/bronze_files/orders");

CREATE TABLE IF NOT EXISTS bronze_customers
USING PARQUET
OPTIONS (path "/Volumes/workspace/customer360/bronze_files/customers");

CREATE TABLE IF NOT EXISTS bronze_order_items
USING PARQUET
OPTIONS (path "/Volumes/workspace/customer360/bronze_files/order_items");

-- Verify row counts
SELECT
  'bronze_orders'      AS table_name, COUNT(*) AS row_count FROM bronze_orders
UNION ALL
SELECT 'bronze_customers',              COUNT(*) FROM bronze_customers
UNION ALL
SELECT 'bronze_order_items',            COUNT(*) FROM bronze_order_items;
