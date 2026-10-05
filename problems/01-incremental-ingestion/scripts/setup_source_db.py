"""
Creates retailco_ tables in PostgreSQL and loads synthetic customer/order data.
Run once to set up the source database for Problem 01.
"""
import psycopg2
import random
import yaml
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"

with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)["source"]["postgres"]

conn = psycopg2.connect(
    host=cfg["host"], port=cfg["port"], database=cfg["database"],
    user=cfg["username"], password=cfg["password"]
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SET search_path TO public;")

print("Connected to PostgreSQL", cfg["host"])

# ── Create tables ──────────────────────────────────────────────────────────────

cur.execute("""
DROP TABLE IF EXISTS retailco_order_items;
DROP TABLE IF EXISTS retailco_orders;
DROP TABLE IF EXISTS retailco_customers;
DROP TABLE IF EXISTS retailco_pipeline_watermarks;
""")

cur.execute("""
CREATE TABLE retailco_customers (
    customer_id   BIGINT PRIMARY KEY,
    email         VARCHAR(255),
    name          VARCHAR(255),
    region        VARCHAR(50),
    tier          VARCHAR(20),
    created_at    TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP NOT NULL
);
CREATE INDEX idx_customers_updated_at ON retailco_customers(updated_at);
""")

cur.execute("""
CREATE TABLE retailco_orders (
    order_id      BIGINT PRIMARY KEY,
    customer_id   BIGINT,
    status        VARCHAR(20),
    total_amount  NUMERIC(12,2),
    region        VARCHAR(50),
    created_at    TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP NOT NULL
);
CREATE INDEX idx_orders_updated_at ON retailco_orders(updated_at);
CREATE INDEX idx_orders_customer_id ON retailco_orders(customer_id);
""")

cur.execute("""
CREATE TABLE retailco_order_items (
    item_id       BIGINT PRIMARY KEY,
    order_id      BIGINT,
    product_id    BIGINT,
    quantity      INT,
    unit_price    NUMERIC(10,2),
    created_at    TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP NOT NULL
);
CREATE INDEX idx_items_updated_at ON retailco_order_items(updated_at);
""")

cur.execute("""
CREATE TABLE retailco_pipeline_watermarks (
    pipeline_name  VARCHAR(100) PRIMARY KEY,
    last_watermark TIMESTAMP,
    last_run_at    TIMESTAMP,
    status         VARCHAR(20)
);
""")

print("Tables created.")

# ── Synthetic data ─────────────────────────────────────────────────────────────

random.seed(42)

REGIONS = ["North", "South", "East", "West"]
TIERS   = ["standard", "standard", "standard", "premium", "premium", "enterprise"]
STATUSES = ["pending", "confirmed", "shipped", "delivered", "delivered", "delivered", "cancelled"]
NAMES = [
    "Alice Johnson", "Bob Smith", "Carol White", "David Lee", "Emma Davis",
    "Frank Miller", "Grace Wilson", "Henry Moore", "Isla Taylor", "Jack Brown",
    "Karen Thomas", "Liam Martin", "Mia Jackson", "Noah Harris", "Olivia Clark",
    "Paul Lewis", "Quinn Robinson", "Rachel Walker", "Sam Hall", "Tina Allen"
]

base_time = datetime(2024, 1, 1)

def rand_ts(start_offset_days=0, end_offset_days=180):
    delta = timedelta(
        days=random.randint(start_offset_days, end_offset_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )
    return base_time + delta

# Customers — 500 records
customers = []
for i in range(1, 501):
    created = rand_ts(0, 120)
    updated = created + timedelta(days=random.randint(0, 60))
    name = random.choice(NAMES) + f" {i}"
    customers.append((
        i,
        f"customer{i}@retailco.com",
        name,
        random.choice(REGIONS),
        random.choice(TIERS),
        created,
        updated
    ))

cur.executemany("""
    INSERT INTO retailco_customers
        (customer_id, email, name, region, tier, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
""", customers)
print(f"Inserted {len(customers)} customers.")

# Orders — 5000 records
orders = []
for i in range(1, 5001):
    cust_id = random.randint(1, 500)
    created = rand_ts(0, 150)
    updated = created + timedelta(hours=random.randint(0, 48))
    orders.append((
        i,
        cust_id,
        random.choice(STATUSES),
        round(random.uniform(20, 2000), 2),
        random.choice(REGIONS),
        created,
        updated
    ))

cur.executemany("""
    INSERT INTO retailco_orders
        (order_id, customer_id, status, total_amount, region, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
""", orders)
print(f"Inserted {len(orders)} orders.")

# Order items — 3 items per order on average = ~15000 records
items = []
item_id = 1
for order_id, _, _, _, _, created, updated in orders:
    for _ in range(random.randint(1, 5)):
        items.append((
            item_id,
            order_id,
            random.randint(1, 200),
            random.randint(1, 10),
            round(random.uniform(5, 500), 2),
            created,
            updated
        ))
        item_id += 1

cur.executemany("""
    INSERT INTO retailco_order_items
        (item_id, order_id, product_id, quantity, unit_price, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
""", items)
print(f"Inserted {len(items)} order items.")

# Seed watermarks table with epoch start
cur.execute("""
    INSERT INTO retailco_pipeline_watermarks (pipeline_name, last_watermark, last_run_at, status)
    VALUES ('orders_incremental', '2024-01-01 00:00:00', NOW(), 'success')
""")
print("Watermark table seeded.")

# ── Verify ─────────────────────────────────────────────────────────────────────

for table in ["retailco_customers", "retailco_orders", "retailco_order_items", "retailco_pipeline_watermarks"]:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"  {table}: {cur.fetchone()[0]} rows")

cur.close()
conn.close()
print("\nSource database ready.")
