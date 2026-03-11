"""
Manage Genie Space creation/update across environments.
Genie Spaces are not yet a native DABs resource, so we automate via REST API.
Run this script as a post-deploy step in your Azure DevOps pipeline.

Usage:
    python scripts/manage_genie_space.py --target dev
    python scripts/manage_genie_space.py --target prod
"""

import argparse
import json
import os
import requests

ENV_CONFIG = {
    "dev": {
        "host": "https://adb-<DEV_WORKSPACE_ID>.azuredatabricks.net",
        "catalog": "dev_catalog",
        "schema": "dev_schema",
        "warehouse_id": "<DEV_WAREHOUSE_ID>",
    },
    "staging": {
        "host": "https://adb-<STAGING_WORKSPACE_ID>.azuredatabricks.net",
        "catalog": "staging_catalog",
        "schema": "staging_schema",
        "warehouse_id": "<STAGING_WAREHOUSE_ID>",
    },
    "prod": {
        "host": "https://adb-<PROD_WORKSPACE_ID>.azuredatabricks.net",
        "catalog": "prod_catalog",
        "schema": "prod_schema",
        "warehouse_id": "<PROD_WAREHOUSE_ID>",
    },
}

GOLD_TABLES = [
    "gold_daily_revenue",
    "gold_category_summary",
    "gold_customer_ltv",
]

SAMPLE_QUESTIONS = [
    "What was the total revenue last week?",
    "Which product category generates the most revenue?",
    "Who are our top 5 customers by lifetime value?",
    "Show me daily order trends",
]


def get_token():
    token = os.environ.get("DATABRICKS_TOKEN")
    if not token:
        raise EnvironmentError("Set DATABRICKS_TOKEN environment variable")
    return token


def create_or_update_genie_space(target: str):
    cfg = ENV_CONFIG[target]
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    table_refs = [f"{cfg['catalog']}.{cfg['schema']}.{t}" for t in GOLD_TABLES]

    payload = {
        "display_name": f"[{target}] Orders Analytics Genie Space",
        "description": (
            "Explore order analytics using natural language. "
            "Ask about revenue, product categories, and customer value."
        ),
        "warehouse_id": cfg["warehouse_id"],
        "table_identifiers": table_refs,
        "sample_questions": SAMPLE_QUESTIONS,
    }

    url = f"{cfg['host']}/api/2.0/genie/spaces"
    print(f"Creating Genie Space in {target} environment...")
    print(f"  URL: {url}")
    print(f"  Tables: {table_refs}")

    resp = requests.post(url, headers=headers, json=payload, timeout=30)

    if resp.status_code == 200:
        space_id = resp.json().get("space_id", "unknown")
        print(f"Genie Space created successfully! ID: {space_id}")
        print(f"  Access at: {cfg['host']}/genie/rooms/{space_id}")
        return space_id
    else:
        print(f"Error ({resp.status_code}): {resp.text}")
        resp.raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Genie Spaces")
    parser.add_argument("--target", choices=["dev", "staging", "prod"], required=True)
    args = parser.parse_args()
    create_or_update_genie_space(args.target)
