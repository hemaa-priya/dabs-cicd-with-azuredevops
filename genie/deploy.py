"""
Deploy Genie Spaces across environments using the serialized_space API.

Reads parameterized space definitions from genie/spaces/*.json,
replaces {{catalog}} and {{schema}} with env-specific values,
and creates or updates each space via the Genie REST API.

Usage:
    python genie/deploy.py --target dev
    python genie/deploy.py --target prod
    python genie/deploy.py --target dev --export customer_summary   # re-export from UI

Auth (pick one):
    DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET  (OAuth M2M - preferred)
    DATABRICKS_TOKEN                                  (PAT - fallback)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
DEPLOYED_PATH = SCRIPT_DIR / "deployed_spaces.json"
SPACES_DIR = SCRIPT_DIR / "spaces"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {path}")


def get_token(host):
    """Get an access token via OAuth M2M, env-var PAT, or Databricks CLI."""
    client_id = os.environ.get("DATABRICKS_CLIENT_ID")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")

    if client_id and client_secret:
        resp = requests.post(
            f"{host}/oidc/v1/token",
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            auth=(client_id, client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    token = os.environ.get("DATABRICKS_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["databricks", "auth", "token", "--host", host],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            token = data.get("access_token")
            if token:
                print(f"  Using token from Databricks CLI for {host}")
                return token
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    print("ERROR: No auth found. Set DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET,")
    print("       DATABRICKS_TOKEN, or configure `databricks auth login`.")
    sys.exit(1)


def render_serialized_space(serialized_space, catalog, schema):
    """Replace {{catalog}} and {{schema}} placeholders in the serialized space."""
    raw = json.dumps(serialized_space)
    raw = raw.replace("{{catalog}}", catalog)
    raw = raw.replace("{{schema}}", schema)
    return raw


def deploy_space(space_name, target, config, deployed):
    """Deploy a single Genie Space to the target environment."""
    space_path = SPACES_DIR / f"{space_name}.json"
    if not space_path.exists():
        print(f"  ERROR: {space_path} not found")
        return

    space_def = load_json(space_path)
    target_cfg = config["targets"][target]

    title = f"{target_cfg['title_prefix']} {space_def['title']}"
    description = space_def.get("description", "")
    warehouse_id = target_cfg["warehouse_id"]
    host = target_cfg["host"]

    serialized_json = render_serialized_space(
        space_def["serialized_space"],
        target_cfg["catalog"],
        target_cfg["schema"],
    )

    token = get_token(host)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    existing_id = deployed.get(target, {}).get(space_name)

    if existing_id:
        # --- UPDATE existing space ---
        print(f"  Updating '{title}' (id: {existing_id})...")
        payload = {
            "title": title,
            "description": description,
            "warehouse_id": warehouse_id,
            "serialized_space": serialized_json,
        }
        resp = requests.patch(
            f"{host}/api/2.0/genie/spaces/{existing_id}",
            headers=headers,
            json=payload,
            timeout=60,
        )
    else:
        # --- CREATE new space ---
        print(f"  Creating '{title}'...")
        payload = {
            "title": title,
            "description": description,
            "warehouse_id": warehouse_id,
            "serialized_space": serialized_json,
        }
        resp = requests.post(
            f"{host}/api/2.0/genie/spaces",
            headers=headers,
            json=payload,
            timeout=60,
        )

    if resp.status_code in (200, 201):
        result = resp.json()
        space_id = result.get("space_id", existing_id)
        action = "Updated" if existing_id else "Created"
        print(f"  {action}: {host}/explore/genie/rooms/{space_id}")

        if target not in deployed:
            deployed[target] = {}
        deployed[target][space_name] = space_id
        save_json(DEPLOYED_PATH, deployed)
        return space_id
    else:
        print(f"  FAILED ({resp.status_code}): {resp.text}")
        sys.exit(1)


def export_space(space_name, target, config, deployed):
    """Re-export a space from the workspace UI back to the local JSON file."""
    space_id = deployed.get(target, {}).get(space_name)
    if not space_id:
        print(f"  ERROR: No deployed space_id for '{space_name}' in {target}")
        sys.exit(1)

    target_cfg = config["targets"][target]
    host = target_cfg["host"]
    token = get_token(host)
    headers = {"Authorization": f"Bearer {token}"}

    print(f"  Exporting '{space_name}' from {target} (id: {space_id})...")
    resp = requests.get(
        f"{host}/api/2.0/genie/spaces/{space_id}?include_serialized_space=true",
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    serialized = json.loads(data["serialized_space"])

    catalog = target_cfg["catalog"]
    schema = target_cfg["schema"]
    raw = json.dumps(serialized)
    raw = raw.replace(f"{catalog}.{schema}.", "{{catalog}}.{{schema}}.")
    serialized = json.loads(raw)

    # Keep join_spec IDs — the API requires them

    space_def = {
        "title": data["title"].replace(f"{target_cfg['title_prefix']} ", ""),
        "description": data.get("description", ""),
        "serialized_space": serialized,
    }

    out_path = SPACES_DIR / f"{space_name}.json"
    save_json(out_path, space_def)
    print(f"  Exported to {out_path}")
    print("  Review the file, commit, and deploy to other environments.")


def main():
    parser = argparse.ArgumentParser(description="Deploy or export Genie Spaces")
    parser.add_argument("--target", choices=["dev", "prod"], required=True)
    parser.add_argument("--export", metavar="SPACE_NAME",
                        help="Re-export a space from workspace back to local JSON")
    parser.add_argument("--export-all", action="store_true",
                        help="Export all spaces registered in deployed_spaces.json for the target")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    deployed = load_json(DEPLOYED_PATH)

    if args.export:
        export_space(args.export, args.target, config, deployed)
        return

    if args.export_all:
        target_spaces = deployed.get(args.target, {})
        if not target_spaces:
            print(f"No deployed spaces found for {args.target} in deployed_spaces.json")
            return
        print(f"Exporting {len(target_spaces)} Genie Space(s) from {args.target}...")
        for space_name in target_spaces:
            try:
                export_space(space_name, args.target, config, deployed)
            except Exception as e:
                print(f"  WARNING: Failed to export '{space_name}': {e}")
        print("\nDone.")
        return

    space_files = sorted(SPACES_DIR.glob("*.json"))
    if not space_files:
        print("No space definitions found in genie/spaces/")
        return

    print(f"Deploying {len(space_files)} Genie Space(s) to {args.target}...")
    print(f"  Host: {config['targets'][args.target]['host']}")
    print(f"  Catalog: {config['targets'][args.target]['catalog']}")
    print(f"  Schema: {config['targets'][args.target]['schema']}")
    print()

    for sf in space_files:
        deploy_space(sf.stem, args.target, config, deployed)

    print("\nDone.")


if __name__ == "__main__":
    main()
