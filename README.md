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
│   ├── dlt_refresh_job.yml                 # Job to trigger the DLT pipeline
│   └── genie_space.yml                     # Genie Space reference (REST API managed)
├── src/
│   ├── notebooks/
│   │   ├── 01_ingest_raw_data.py           # Bronze ingestion notebook
│   │   ├── 02_transform_silver.py          # Silver transformation notebook
│   │   └── 03_gold_aggregations.py         # Gold aggregation notebook
│   └── pipelines/
│       └── dlt_orders_pipeline.py          # DLT pipeline definition
├── scripts/
│   ├── deploy.sh                           # Local deploy helper
│   ├── destroy.sh                          # Teardown helper
│   └── manage_genie_space.py               # Genie Space REST API automation
├── .azure-devops/
│   ├── azure-pipelines.yml                 # Main CI/CD pipeline (validate → staging → prod)
│   └── pr-validation.yml                   # Lightweight PR validation pipeline
└── .gitignore
```

## Architecture / Flow

```
Developer Workstation          Azure DevOps              Databricks Workspaces
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│                 │     │                      │     │                      │
│  Edit code      │────▶│  PR ─▶ Validate      │     │  DEV workspace       │
│  databricks     │     │       (lint, schema)  │     │  (development mode)  │
│  bundle deploy  │     │                      │     │                      │
│  -t dev         │     │  Merge ─▶ Deploy     │────▶│  STAGING workspace   │
│                 │     │           Staging     │     │  (integration tests) │
│                 │     │                      │     │                      │
│                 │     │  Approve ─▶ Deploy   │────▶│  PROD workspace      │
│                 │     │             Prod     │     │  (production mode)   │
└─────────────────┘     └──────────────────────┘     └──────────────────────┘
```

## What Gets Deployed

| Artifact | DABs Resource | Description |
|----------|---------------|-------------|
| ETL Job | `etl_orders_job` | 3-task workflow: ingest → transform → aggregate |
| DLT Pipeline | `orders_dlt_pipeline` | Streaming medallion pipeline with data quality |
| DLT Refresh Job | `dlt_refresh_job` | Scheduled trigger for the DLT pipeline |
| Genie Space | REST API script | NL exploration of gold tables |
| Notebooks | Bundled in jobs | 3 parameterized notebooks for the ETL job |

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

| Placeholder | Replace With |
|-------------|-------------|
| `<DEV_WORKSPACE_ID>` | Your dev workspace ID (from the URL) |
| `<STAGING_WORKSPACE_ID>` | Your staging workspace ID |
| `<PROD_WORKSPACE_ID>` | Your prod workspace ID |
| `<DEV_WAREHOUSE_ID>` | SQL warehouse ID in dev |
| `<STAGING_WAREHOUSE_ID>` | SQL warehouse ID in staging |
| `<PROD_WAREHOUSE_ID>` | SQL warehouse ID in prod |
| `cicd-service-principal` | Your service principal name |

Also update `scripts/manage_genie_space.py` with the same values.

---

### Step 3: Set Up Azure DevOps

#### 3a. Create Variable Group

In Azure DevOps > Pipelines > Library, create a variable group named `databricks-cicd-secrets`:

| Variable | Value | Secret? |
|----------|-------|---------|
| `DATABRICKS_HOST_DEV` | `https://adb-xxx.azuredatabricks.net` | No |
| `DATABRICKS_HOST_STAGING` | `https://adb-yyy.azuredatabricks.net` | No |
| `DATABRICKS_HOST_PROD` | `https://adb-zzz.azuredatabricks.net` | No |
| `DATABRICKS_CLIENT_ID` | Service principal app ID | Yes |
| `DATABRICKS_CLIENT_SECRET` | Service principal secret | Yes |
| `DATABRICKS_TOKEN_STAGING` | PAT or OAuth token for staging | Yes |
| `DATABRICKS_TOKEN_PROD` | PAT or OAuth token for prod | Yes |

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

### Step 5: CI/CD Flow (How It Works)

```
1. Developer creates a feature branch
   └── git checkout -b feature/add-new-metric

2. Makes changes to notebooks, jobs, or pipeline config
   └── edits src/notebooks/03_gold_aggregations.py

3. Opens a Pull Request → main
   └── Azure DevOps triggers PR validation pipeline
       ├── databricks bundle validate -t dev
       ├── databricks bundle validate -t prod
       ├── ruff lint check
       └── security scan (no hardcoded tokens)

4. PR is approved and merged to main
   └── Azure DevOps triggers main CI/CD pipeline
       ├── Stage: DeployStaging
       │   ├── databricks bundle validate -t staging
       │   ├── databricks bundle deploy -t staging
       │   ├── databricks bundle run etl_orders_job -t staging  (integration test)
       │   └── python manage_genie_space.py --target staging
       │
       └── Stage: DeployProduction (after manual approval)
           ├── databricks bundle validate -t prod
           ├── databricks bundle deploy -t prod
           └── python manage_genie_space.py --target prod

5. Production is live with the same code validated in staging
```

---

### Step 6: Verify the Deployment

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

# Or use the helper
./scripts/destroy.sh dev
```

---

## Key Best Practices Applied

Based on [Databricks CI/CD Best Practices](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/best-practices):

| Principle | How It's Applied |
|-----------|-----------------|
| **Version control everything** | All code, config, and pipeline YAML in Git |
| **Automate testing** | PR validation, bundle validate, integration tests in staging |
| **Infrastructure as Code** | All resources defined in YAML via DABs |
| **Environment isolation** | Separate workspaces for dev/staging/prod with parameterized catalogs |
| **Match cloud ecosystem tools** | Azure DevOps + DABs (Azure-native) |
| **Monitor and automate rollback** | Email notifications on failure, approval gates before prod |
| **Unified asset management** | Single bundle packages jobs, pipelines, notebooks together |

---

## Extending This Demo

- **Add dashboards**: Export with `databricks bundle generate dashboard` and add to `resources/`
- **Add ML models**: Use MLOps Stacks template for model training + deployment jobs
- **Add alerts**: See `alerts_guidance.md` in the DABs skill for SQL alert resource definitions
- **Multi-repo setup**: Separate code repo from bundle config repo for larger teams
