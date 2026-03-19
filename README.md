# Databricks Asset Bundles + Azure DevOps CI/CD Demo

End-to-end example of promoting Databricks artifacts (jobs, DLT pipelines, notebooks, and Genie Spaces) from a **dev** workspace to **production** using **Databricks Asset Bundles (DABs)** and **Azure DevOps Pipelines**.

Reference: [Databricks CI/CD Best Practices](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/best-practices)

---

## Project Structure

```
acc_devops/
├── databricks.yml                          # Main bundle config (targets, variables)
├── resources/
│   ├── etl_job.yml                         # Multi-task ETL job (bronze → silver → gold)
│   ├── dlt_pipeline.yml                    # Lakeflow Declarative Pipeline (DLT)
│   └── dlt_refresh_job.yml                 # Job to trigger the DLT pipeline
├── src/
│   ├── notebooks/
│   │   ├── 01_ingest_raw_data.py           # Bronze ingestion notebook
│   │   ├── 02_transform_silver.py          # Silver transformation notebook
│   │   └── 03_gold_aggregations.py         # Gold aggregation notebook
│   └── pipelines/
│       └── dlt_orders_pipeline.py          # DLT pipeline definition
├── genie/
│   ├── deploy.py                           # Genie Space deploy/export script (REST API)
│   ├── config.json                         # Per-target host, catalog, schema, warehouse
│   ├── deployed_spaces.json                # Tracks deployed space IDs per environment
│   └── spaces/
│       └── weather_genie.json              # Parameterized space definition (exported)
├── .azure-devops/
│   └── azure-pipelines.yml                 # CI/CD pipeline (dev branch → DEV, main → PROD)
└── .gitignore
```

## Architecture / Flow

```
Developer Workstation          Azure DevOps              Databricks Workspaces
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│                 │     │                      │     │                      │
│  Edit code      │────▶│  PR ─▶ Validate      │     │  DEV workspace       │
│  databricks     │     │       (lint, schema) │     │  (development mode)  │
│  bundle deploy  │     │                      │     │                      │
│  -t dev         │     │  Merge ─▶ Deploy     │────▶│  STAGING workspace   │
│                 │     │           Staging    │     │  (integration tests) │
│                 │     │                      │     │                      │
│                 │     │  Approve ─▶ Deploy   │────▶│  PROD workspace      │
│                 │     │             Prod     │     │  (production mode)   │
└─────────────────┘     └──────────────────────┘     └──────────────────────┘
```

## What Gets Deployed


| Artifact        | DABs Resource                | Description                                     |
| --------------- | ---------------------------- | ----------------------------------------------- |
| ETL Job         | `etl_orders_job`             | 3-task workflow: ingest → transform → aggregate |
| DLT Pipeline    | `orders_dlt_pipeline`        | Streaming medallion pipeline with data quality  |
| DLT Refresh Job | `dlt_refresh_job`            | Scheduled trigger for the DLT pipeline          |
| Genie Space     | `genie/deploy.py` (REST API) | NL exploration of gold tables                   |
| Notebooks       | Bundled in jobs              | 3 parameterized notebooks for the ETL job       |


---

## Implementation Instructions

### Prerequisites

1. **Databricks CLI** (v0.236.0+):
  ```bash
   curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
   databricks --version
  ```
2. **Two or more Azure Databricks workspaces** (dev, staging/prod) with Unity Catalog enabled
3. **Azure DevOps project** with a Git repository
4. **Service Principal** for CI/CD authentication (recommended: workload identity federation)

---

### Step 1: Configure Databricks Authentication

#### Option A: Databricks CLI Profiles (for local development)

```bash
# Configure dev profile
databricks configure --profile dev-profile
# Enter: host = https://adb-<DEV_WORKSPACE_ID>.azuredatabricks.net
# Enter: personal access token

# Configure prod profile
databricks configure --profile prod-profile
```

Then update `databricks.yml` targets to use profiles:

```yaml
targets:
  dev:
    workspace:
      profile: dev-profile
```

#### Option B: Service Principal with OAuth (for CI/CD — recommended)

1. Create a service principal in your Azure Databricks account console
2. Grant it workspace access in both dev and prod workspaces
3. Generate an OAuth secret
4. Store credentials in Azure DevOps variable group (see Step 3)

Reference: [Workload Identity Federation for CI/CD](https://docs.databricks.com/dev-tools/auth/oauth-federation-provider.html)

---

### Step 2: Update Placeholder Values

Edit `databricks.yml` and replace all placeholders:


| Placeholder              | Replace With                         |
| ------------------------ | ------------------------------------ |
| `<DEV_WORKSPACE_ID>`     | Your dev workspace ID (from the URL) |
| `<STAGING_WORKSPACE_ID>` | Your staging workspace ID            |
| `<PROD_WORKSPACE_ID>`    | Your prod workspace ID               |
| `<DEV_WAREHOUSE_ID>`     | SQL warehouse ID in dev              |
| `<STAGING_WAREHOUSE_ID>` | SQL warehouse ID in staging          |
| `<PROD_WAREHOUSE_ID>`    | SQL warehouse ID in prod             |
| `cicd-service-principal` | Your service principal name          |


Also update `genie/config.json` with the same host, catalog, schema, and warehouse ID values.

---

### Step 3: Set Up Azure DevOps

#### 3a. Create Variable Group

In Azure DevOps > Pipelines > Library, create a variable group named `databricks-cicd-secrets`:


| Variable                   | Value                                 | Secret? |
| -------------------------- | ------------------------------------- | ------- |
| `DATABRICKS_HOST_DEV`      | `https://adb-xxx.azuredatabricks.net` | No      |
| `DATABRICKS_HOST_STAGING`  | `https://adb-yyy.azuredatabricks.net` | No      |
| `DATABRICKS_HOST_PROD`     | `https://adb-zzz.azuredatabricks.net` | No      |
| `DATABRICKS_CLIENT_ID`     | Service principal app ID              | Yes     |
| `DATABRICKS_CLIENT_SECRET` | Service principal secret              | Yes     |
| `DATABRICKS_TOKEN_STAGING` | PAT or OAuth token for staging        | Yes     |
| `DATABRICKS_TOKEN_PROD`    | PAT or OAuth token for prod           | Yes     |


#### 3b. Create Environments with Approval Gates

1. Go to **Pipelines > Environments**
2. Create `databricks-staging` (optional: add approval check)
3. Create `databricks-production` (add manual approval from a designated approver)

#### 3c. Create the Pipeline

1. Go to **Pipelines > New Pipeline**
2. Select your Azure Repos Git repository
3. Choose **Existing Azure Pipelines YAML file**
4. Select `.azure-devops/azure-pipelines.yml`
5. Save and run

#### 3d. (Optional) Add PR Validation Policy

1. Go to **Repos > Branches > main > Branch policies**
2. Add a **Build validation** policy
3. Point it to `.azure-devops/pr-validation.yml`

---

### Step 4: Local Development Workflow

```bash
cd acc_devops

# Validate the bundle
databricks bundle validate -t dev

# Deploy to dev workspace
databricks bundle deploy -t dev

# Run the ETL job
databricks bundle run etl_orders_job -t dev

# Run the DLT pipeline
databricks bundle run orders_dlt_pipeline -t dev

# Or use the helper script
./scripts/deploy.sh dev
```

---

### Step 5: Genie Space Deployment (Dev → Prod)

DABs does **not** support Genie Spaces as a resource type. The `genie/deploy.py` script handles Genie Spaces separately via the REST API.

#### Configuration

`genie/config.json` defines per-environment settings:

```json
{
  "targets": {
    "dev":  { "host": "https://adb-<DEV>.azuredatabricks.net",  "catalog": "...", "schema": "...", "warehouse_id": "...", "title_prefix": "[dev]"  },
    "prod": { "host": "https://adb-<PROD>.azuredatabricks.net", "catalog": "...", "schema": "...", "warehouse_id": "...", "title_prefix": "[prod]" }
  }
}
```

#### Authentication

The script checks for credentials in this order:

1. `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` (OAuth M2M — used by CI/CD)
2. `DATABRICKS_TOKEN` (PAT)
3. Databricks CLI auth (`databricks auth token`) — picks up existing CLI profiles

For local use, just make sure your CLI profiles are valid:

```bash
databricks auth login --host https://adb-<DEV>.azuredatabricks.net
databricks auth login --host https://adb-<PROD>.azuredatabricks.net
```

#### Workflow: Promote a Genie Space from Dev to Prod

**1. Create or edit the Genie Space in the dev workspace UI**

**2. Register the space ID** (first time only)

Get the space ID from the URL (`/explore/genie/rooms/<SPACE_ID>`) and add it to `genie/deployed_spaces.json`:

```json
{
  "dev": { "weather_genie": "<SPACE_ID>" },
  "prod": {}
}
```

**3. Export the space from dev**

This pulls the space definition from the dev workspace, replaces catalog/schema values with `{{catalog}}`/`{{schema}}` placeholders, and saves to `genie/spaces/<name>.json`:

```bash
python3 genie/deploy.py --target dev --export weather_genie
```

**4. Deploy to prod**

This reads the exported JSON, substitutes prod catalog/schema values, and creates or updates the space in the prod workspace:

```bash
python3 genie/deploy.py --target prod
```

**5. Commit the exported file**

```bash
git add genie/spaces/weather_genie.json genie/deployed_spaces.json
git commit -m "Update weather_genie space"
git push origin main
```

#### Updating an Existing Genie Space

After making changes to a space in the dev UI, repeat steps 3–5. The script will detect the existing space ID in `deployed_spaces.json` and update it (PATCH) rather than creating a new one.

---

### Step 6: CI/CD Flow (How It Works)

```
1. Developer creates a feature branch
   └── git checkout -b feature/add-new-metric

2. Makes changes to notebooks, jobs, pipeline config, or Genie Spaces
   └── edits src/notebooks/03_gold_aggregations.py
   └── exports updated Genie Space: python3 genie/deploy.py --target dev --export weather_genie

3. Opens a Pull Request → main
   └── Azure DevOps triggers Validate stage
       ├── databricks bundle validate -t dev
       └── databricks bundle validate -t prod

4. Push to dev branch
   └── Azure DevOps triggers DeployDev stage
       ├── databricks bundle validate -t dev
       ├── databricks bundle deploy -t dev
       └── python genie/deploy.py --target dev          (Genie Spaces)

5. PR is approved and merged to main
   └── Azure DevOps triggers DeployProd stage
       ├── databricks bundle validate -t prod
       ├── databricks bundle deploy -t prod              (jobs, pipelines, notebooks)
       └── python genie/deploy.py --target prod          (Genie Spaces)

6. Production is live with the same code validated in dev
```

---

### Step 7: Verify the Deployment

After deploying, verify in each workspace:

1. **Jobs**: Navigate to Workflows. You should see:
  - `[dev] ETL Orders Pipeline`
  - `[dev] DLT Pipeline Refresh`
2. **DLT Pipeline**: Navigate to Spark Declarative Pipelines. You should see:
  - `[dev] Orders DLT Pipeline`
3. **Genie Space**: Navigate to Genie. You should see:
  - `[dev] Orders Analytics Genie Space`
4. **Notebooks**: Check Workspace > Users > your-user > `.bundle/acc-devops-cicd-demo/dev/`

---

### Cleanup

```bash
# Destroy dev resources
databricks bundle destroy -t dev --auto-approve
```

---

## Key Best Practices Applied

Based on [Databricks CI/CD Best Practices](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/best-practices):


| Principle                         | How It's Applied                                                     |
| --------------------------------- | -------------------------------------------------------------------- |
| **Version control everything**    | All code, config, and pipeline YAML in Git                           |
| **Automate testing**              | PR validation, bundle validate, integration tests in staging         |
| **Infrastructure as Code**        | All resources defined in YAML via DABs                               |
| **Environment isolation**         | Separate workspaces for dev/staging/prod with parameterized catalogs |
| **Match cloud ecosystem tools**   | Azure DevOps + DABs (Azure-native)                                   |
| **Monitor and automate rollback** | Email notifications on failure, approval gates before prod           |
| **Unified asset management**      | Single bundle packages jobs, pipelines, notebooks together           |


---

## Extending This Demo

- **Add Genie Spaces**: Create in the dev UI, export with `python3 genie/deploy.py --target dev --export <name>`, deploy to prod
- **Add dashboards**: Export with `databricks bundle generate dashboard` and add to `resources/`
- **Add ML models**: Use MLOps Stacks template for model training + deployment jobs
- **Add alerts**: See `alerts_guidance.md` in the DABs skill for SQL alert resource definitions
- **Multi-repo setup**: Separate code repo from bundle config repo for larger teams

