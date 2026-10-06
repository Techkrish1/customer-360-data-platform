"""
Trigger the Databricks pipeline Workflow and poll until completion.

Workflow: customer-360-pipeline-problem-01
Tasks (in order):
  01_setup_bronze  -> 02_silver_transform -> 03_gold_dimensions
  -> 04_gold_facts -> 05_gold_mart
"""
import time
import yaml
import requests
from pathlib import Path
from datetime import datetime, timezone

CONFIG_PATH = Path(__file__).parents[1] / "config" / "config.yaml"
JOB_ID      = 644685154057195


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def db_post(cfg, path, payload):
    url     = f"{cfg['workspace_url']}/api/2.1/{path}"
    headers = {"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"}
    return requests.post(url, headers=headers, json=payload).json()


def db_get(cfg, path):
    url     = f"{cfg['workspace_url']}/api/2.1/{path}"
    headers = {"Authorization": f"Bearer {cfg['token']}"}
    return requests.get(url, headers=headers).json()


def trigger_run(cfg):
    result = db_post(cfg, "jobs/run-now", {"job_id": JOB_ID})
    if "error_code" in result:
        print(f"  ERROR: {result.get('message','')}")
        return None
    run_id = result.get("run_id")
    print(f"  Run triggered: run_id={run_id}")
    return run_id


def poll_run(cfg, run_id):
    print()
    print("  Polling for completion (auto-terminates on done/failed)...")
    print()

    while True:
        result = db_get(cfg, f"jobs/runs/get?run_id={run_id}")
        state  = result.get("state", {})
        lc     = state.get("life_cycle_state", "UNKNOWN")
        rs     = state.get("result_state", "")
        msg    = state.get("state_message", "")

        ts     = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"  [{ts}]  {lc:<20} {rs:<12} {msg}")

        if lc in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            return rs, result

        time.sleep(15)


def print_task_results(run_result):
    tasks = run_result.get("tasks", [])
    if not tasks:
        return

    print()
    print("  Task results:")
    for t in sorted(tasks, key=lambda x: x.get("task_key", "")):
        state  = t.get("state", {})
        lc     = state.get("life_cycle_state", "?")
        rs     = state.get("result_state", "")
        key    = t.get("task_key", "?")
        dur    = t.get("execution_duration", 0)
        print(f"    {key:<30} {rs or lc:<12} {dur//1000}s")


def run():
    cfg = load_config()["warehouse"]["databricks"]

    print(f"\nDatabricks Pipeline: customer-360-problem-01")
    print(f"  Job ID : {JOB_ID}")
    print(f"  Warehouse: {cfg['workspace_url']}")
    print()

    run_id = trigger_run(cfg)
    if not run_id:
        return

    result_state, run_result = poll_run(cfg, run_id)

    print_task_results(run_result)

    print()
    print("=" * 50)
    print(f"Pipeline result: {result_state}")
    print("=" * 50)

    if result_state == "SUCCESS":
        print("  All 5 SQL notebooks ran successfully.")
        print("  Gold tables are ready in workspace.customer360:")
        print("    silver_orders, silver_customers, silver_order_items")
        print("    gold_dim_customer, gold_dim_product, gold_dim_date")
        print("    gold_fact_orders, gold_fact_order_items")
        print("    gold_mart_rfm")
    else:
        print(f"  Check logs at: {cfg['workspace_url']}/jobs/{JOB_ID}/runs/{run_id}")


if __name__ == "__main__":
    run()
