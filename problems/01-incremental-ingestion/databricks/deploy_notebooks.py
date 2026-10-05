"""
Deploy SQL notebooks to Databricks workspace and create the pipeline Workflow.

What this does:
  1. Creates workspace folder /customer-360-platform/problem-01/
  2. Uploads 5 SQL notebooks (01 - 05)
  3. Creates a Databricks Workflow that runs them in order against the SQL Warehouse
"""
import base64
import json
import yaml
import requests
from pathlib import Path

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"
NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"

WORKSPACE_FOLDER = "/customer-360-platform/problem-01"
WAREHOUSE_ID     = "7936c993ce977595"

NOTEBOOKS = [
    "01_setup_bronze",
    "02_silver_transform",
    "03_gold_dimensions",
    "04_gold_facts",
    "05_gold_mart",
]


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def db_post(cfg, path, payload):
    url = f"{cfg['workspace_url']}/api/2.0/{path}"
    headers = {"Authorization": f"Bearer {cfg['token']}",
               "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()


def db_get(cfg, path):
    url = f"{cfg['workspace_url']}/api/2.0/{path}"
    headers = {"Authorization": f"Bearer {cfg['token']}"}
    return requests.get(url, headers=headers).json()


def create_folder(cfg, path):
    result = db_post(cfg, "workspace/mkdirs", {"path": path})
    if "error_code" in result:
        print(f"  Folder {path}: {result.get('message','')}")
    else:
        print(f"  Folder created: {path}")


def upload_notebook(cfg, name, sql_path):
    content = sql_path.read_text(encoding="utf-8")
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    nb_path = f"{WORKSPACE_FOLDER}/{name}"
    result = db_post(cfg, "workspace/import", {
        "path"      : nb_path,
        "language"  : "SQL",
        "format"    : "SOURCE",
        "overwrite" : True,
        "content"   : encoded,
    })

    if "error_code" in result:
        print(f"  ERROR uploading {name}: {result.get('message','')}")
        return None
    print(f"  Uploaded: {nb_path}")
    return nb_path


def create_workflow(cfg, notebook_paths):
    """Create a Databricks Job (Workflow) that runs notebooks sequentially."""

    # Build task list — each notebook is one task, depends on the previous
    tasks = []
    for i, (name, nb_path) in enumerate(zip(NOTEBOOKS, notebook_paths)):
        task = {
            "task_key"          : name,
            "notebook_task"     : {
                "notebook_path" : nb_path,
                "source"        : "WORKSPACE",
                "warehouse_id"  : WAREHOUSE_ID,
            },
            "sql_task": None,  # notebook_task takes precedence
        }
        # Remove sql_task key — notebook_task is used here
        del task["sql_task"]

        if i > 0:
            task["depends_on"] = [{"task_key": NOTEBOOKS[i - 1]}]

        tasks.append(task)

    payload = {
        "name"    : "customer-360-pipeline-problem-01",
        "tasks"   : tasks,
        "format"  : "MULTI_TASK",
        "tags"    : {"project": "customer-360", "problem": "01"},
    }

    result = db_post(cfg, "jobs/create", payload)
    if "error_code" in result:
        print(f"  ERROR creating workflow: {result.get('message','')}")
        return None

    job_id = result.get("job_id")
    print(f"  Workflow created: job_id={job_id}")
    return job_id


def run():
    cfg = load_config()["warehouse"]["databricks"]

    print(f"Databricks workspace: {cfg['workspace_url']}")
    print()

    # Step 1 — Create workspace folder
    print("Creating workspace folder...")
    create_folder(cfg, "/customer-360-platform")
    create_folder(cfg, WORKSPACE_FOLDER)
    print()

    # Step 2 — Upload notebooks
    print("Uploading SQL notebooks...")
    notebook_paths = []
    for name in NOTEBOOKS:
        sql_file = NOTEBOOKS_DIR / f"{name}.sql"
        if not sql_file.exists():
            print(f"  MISSING: {sql_file}")
            continue
        path = upload_notebook(cfg, name, sql_file)
        if path:
            notebook_paths.append(path)
    print()

    if len(notebook_paths) != len(NOTEBOOKS):
        print("Some notebooks failed to upload — aborting workflow creation.")
        return

    # Step 3 — Create Workflow
    print("Creating Databricks Workflow...")
    job_id = create_workflow(cfg, notebook_paths)
    print()

    if job_id:
        print("=" * 55)
        print("DEPLOYMENT COMPLETE")
        print("=" * 55)
        print(f"  Workspace folder : {WORKSPACE_FOLDER}")
        print(f"  Notebooks        : {len(notebook_paths)}")
        print(f"  Workflow job_id  : {job_id}")
        print()
        print("To run the pipeline:")
        print(f"  Open: {cfg['workspace_url']}/jobs/{job_id}")
        print("  Or run: python run_workflow.py")


if __name__ == "__main__":
    run()
