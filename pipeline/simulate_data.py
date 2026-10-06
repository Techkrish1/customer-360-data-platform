"""
Simulates business activity in PostgreSQL.
Run this before any pipeline run to generate new and changed records.
"""
import psycopg2
import random
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parents[1] / "config" / "config.yaml"

REGIONS  = ["North", "South", "East", "West"]
TIERS    = ["standard", "standard", "premium", "enterprise"]
STATUSES = ["pending", "confirmed", "shipped"]
STATUS_TRANSITIONS = {"pending": "confirmed", "confirmed": "shipped", "shipped": "delivered"}


def get_connection():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)["source"]["postgres"]
    conn = psycopg2.connect(
        host=cfg["host"], port=cfg["port"], database=cfg["database"],
        user=cfg["username"], password=cfg["password"]
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO public;")
    return conn, cur


def simulate(new_orders=100, status_updates=30, new_customers=10):
    conn, cur = get_connection()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Get current max IDs so we don't collide with existing rows
    cur.execute("SELECT COALESCE(MAX(customer_id), 0) FROM retailco_customers")
    max_customer = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(order_id), 0) FROM retailco_orders")
    max_order = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(item_id), 0) FROM retailco_order_items")
    max_item = cur.fetchone()[0]

    # ── 1. New customers ──────────────────────────────────────────────────────
    new_customer_ids = []
    for i in range(new_customers):
        cid = max_customer + i + 1
        new_customer_ids.append(cid)
        ts = now - timedelta(minutes=random.randint(5, 60))
        cur.execute("""
            INSERT INTO retailco_customers
                (customer_id, email, name, region, tier, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (cid, f"customer{cid}@retailco.com", f"Customer {cid}",
              random.choice(REGIONS), random.choice(TIERS), ts, ts))

    # ── 2. New orders (spread across existing + new customers) ────────────────
    cur.execute("SELECT customer_id FROM retailco_customers ORDER BY RANDOM() LIMIT 200")
    all_customer_ids = [r[0] for r in cur.fetchall()] + new_customer_ids

    new_order_ids = []
    for i in range(new_orders):
        oid = max_order + i + 1
        new_order_ids.append(oid)
        ts = now - timedelta(minutes=random.randint(1, 90))
        cur.execute("""
            INSERT INTO retailco_orders
                (order_id, customer_id, status, total_amount, region, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (oid, random.choice(all_customer_ids), random.choice(STATUSES),
              round(random.uniform(25, 1500), 2), random.choice(REGIONS), ts, ts))

    # ── 3. Order items for new orders ─────────────────────────────────────────
    item_id = max_item + 1
    items_added = 0
    for oid in new_order_ids:
        for _ in range(random.randint(1, 4)):
            cur.execute("""
                INSERT INTO retailco_order_items
                    (item_id, order_id, product_id, quantity, unit_price, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (item_id, oid, random.randint(1, 200),
                  random.randint(1, 5), round(random.uniform(10, 400), 2), now, now))
            item_id += 1
            items_added += 1

    # ── 4. Status transitions on existing orders ──────────────────────────────
    cur.execute("""
        SELECT order_id, status FROM retailco_orders
        WHERE status IN ('pending', 'confirmed', 'shipped')
        ORDER BY RANDOM() LIMIT %s
    """, (status_updates,))

    updated = 0
    for order_id, current_status in cur.fetchall():
        new_status = STATUS_TRANSITIONS.get(current_status)
        if new_status:
            ts = now - timedelta(minutes=random.randint(1, 45))
            cur.execute("""
                UPDATE retailco_orders
                SET status = %s, updated_at = %s
                WHERE order_id = %s
            """, (new_status, ts, order_id))
            updated += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM retailco_customers")
    total_customers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM retailco_orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM retailco_order_items")
    total_items = cur.fetchone()[0]

    print(f"Simulation complete — {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"")
    print(f"  New customers added  : {new_customers}")
    print(f"  New orders inserted  : {new_orders}")
    print(f"  Order items added    : {items_added}")
    print(f"  Order statuses moved : {updated}")
    print(f"")
    print(f"Database totals after simulation:")
    print(f"  retailco_customers   : {total_customers} rows")
    print(f"  retailco_orders      : {total_orders} rows")
    print(f"  retailco_order_items : {total_items} rows")
    print(f"")
    print(f"Pipeline will detect ~{new_orders + updated} changed records on next run.")

    conn.close()


if __name__ == "__main__":
    simulate(new_orders=100, status_updates=30, new_customers=10)
