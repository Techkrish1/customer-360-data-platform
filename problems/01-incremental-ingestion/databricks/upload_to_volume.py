"""
Upload Bronze Parquet files from S3 to Databricks Unity Catalog Volume.

Flow:
  S3 Bronze (Parquet) -> Databricks Volume /Volumes/workspace/customer360/bronze_files/{table}/

Run AFTER 01_extract_bronze.py to sync Bronze data into Databricks.
Then trigger the Databricks SQL Workflow (run_workflow.py) to process it.
"""
import yaml
import boto3
import requests
from pathlib import Path

CONFIG_PATH = Path(__file__).parents[3] / "shared" / "config" / "config.yaml"

VOLUME_BASE  = "Volumes/workspace/customer360/bronze_files"
TABLES       = ["orders", "customers", "order_items"]


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def files_api_url(workspace_url, volume_path):
    host = workspace_url.rstrip("/")
    return f"{host}/api/2.1/fs/files/{volume_path}"


def list_bronze_files(s3, bucket, table):
    prefix = f"customer-360/bronze/{table}/"
    paginator = s3.get_paginator("list_objects_v2")
    files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                files.append(obj["Key"])
    return files


def upload_parquet(workspace_url, token, volume_path, data_bytes):
    url = files_api_url(workspace_url, volume_path)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type" : "application/octet-stream",
    }
    resp = requests.put(url, headers=headers, data=data_bytes)
    return resp.status_code in (200, 201, 204)


def run():
    cfg    = load_config()
    s3_cfg = cfg["staging"]["s3"]
    db_cfg = cfg["warehouse"]["databricks"]

    bucket        = s3_cfg["bucket"]
    workspace_url = db_cfg["workspace_url"]
    token         = db_cfg["token"]

    s3 = boto3.client(
        "s3",
        aws_access_key_id     = s3_cfg["aws_access_key_id"],
        aws_secret_access_key = s3_cfg["aws_secret_access_key"],
        region_name           = s3_cfg["region"],
    )

    print("Syncing Bronze files: S3 -> Databricks Volume")
    print(f"  Source bucket : s3://{bucket}/customer-360/bronze/")
    print(f"  Target volume : /{VOLUME_BASE}/")
    print()

    total_uploaded = 0
    total_files    = 0

    for table in TABLES:
        files = list_bronze_files(s3, bucket, table)
        total_files += len(files)
        uploaded = 0

        print(f"  {table}: {len(files)} Parquet files")

        for key in files:
            obj        = s3.get_object(Bucket=bucket, Key=key)
            data_bytes = obj["Body"].read()

            # flatten path: just use filename, prefix with table
            filename     = Path(key).name
            volume_path  = f"{VOLUME_BASE}/{table}/{filename}"

            ok = upload_parquet(workspace_url, token, volume_path, data_bytes)
            if ok:
                uploaded += 1
            else:
                print(f"    FAILED: {key}")

        print(f"    Uploaded: {uploaded}/{len(files)}")
        total_uploaded += uploaded

    print()
    print(f"Done. {total_uploaded}/{total_files} files uploaded to Databricks Volume.")
    print()
    print("Next: run the Databricks pipeline")
    print("  python run_workflow.py")


if __name__ == "__main__":
    run()
