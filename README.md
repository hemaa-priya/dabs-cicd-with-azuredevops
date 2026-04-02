# Databricks Asset Bundles + Azure DevOps CI/CD

End-to-end example of promoting Databricks artifacts (jobs, DLT pipelines, notebooks) from **dev** to **prod** using **Databricks Asset Bundles (DABs)** and **Azure DevOps Pipelines**.

---

## Project Structure

```
hp_cicd2/
├── databricks.yml                          # Bundle config (variables, targets)
├── resources/
│   ├── etl_job.yml                         # Multi-task ETL job (bronze → silver → gold)
│   ├── dlt_pipeline.yml                    # Lakeflow Declarative Pipeline (DLT)
│   └── dlt_refresh_job.yml                 # Scheduled job to refresh the DLT pipeline
├── src/
│   ├── notebooks/
│   │   ├── 01_ingest_raw_data.py           # Bronze ingestion
│   │   ├── 02_transform_silver.py          # Silver transformation
│   │   └── 03_gold_aggregations.py         # Gold aggregations
│   └── pipelines/
│       └── dlt_orders_pipeline.py          # DLT pipeline definition (Auto Loader → medallion)
├── scripts/
│   ├── deploy.sh                           # Local deploy helper
│   └── destroy.sh                          # Tear down deployed resources
├── .azure-devops/
│   └── azure-pipelines.yml                 # CI/CD pipeline definition
└── .gitignore
```

---

## What Gets Deployed

| Artifact        | DABs Resource           | Description                                     |
| --------------- | ----------------------- | ----------------------------------------------- |
| ETL Job         | `etl_orders_job`        | 3-task workflow: ingest → transform → aggregate  |
| DLT Pipeline    | `orders_dlt_pipeline`   | Streaming medallion pipeline with data quality   |
| DLT Refresh Job | `dlt_refresh_job`       | Daily scheduled trigger for the DLT pipeline     |
| Notebooks       | Bundled in jobs         | 3 parameterized notebooks for the ETL job        |

---

## CI/CD Flow

```
PR to main        → Validate stage (bundle validate for dev + prod)
Push to dev branch → Deploy to DEV workspace
Merge to main      → Deploy to PROD workspace
```

Authentication uses OAuth M2M via a service principal. Secrets are stored in the Azure DevOps variable group `hp_dbr_secrets`.

---

## Getting Started

### Prerequisites

- **Databricks CLI** (v0.236.0+)
- **Two Azure Databricks workspaces** (dev + prod) with Unity Catalog enabled
- **Azure DevOps project** with a Git repository
- **Service Principal** for CI/CD authentication

### Local Development

```bash
# Validate the bundle
databricks bundle validate -t dev

# Deploy to dev workspace
databricks bundle deploy -t dev

# Run the ETL job
databricks bundle run etl_orders_job -t dev

# Run the DLT pipeline
databricks bundle run orders_dlt_pipeline -t dev
```

Or use the helper script:

```bash
./scripts/deploy.sh dev
```

### Azure DevOps Setup

1. **Variable Group** — create `hp_dbr_secrets` in Pipelines > Library with:
   - `DATABRICKS_HOST_DEV` / `DATABRICKS_HOST_PROD` (workspace URLs)
   - `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` (service principal credentials, mark as secret)

2. **Pipeline** — create a new pipeline pointing to `.azure-devops/azure-pipelines.yml`

3. **Branch Policy** (optional) — add build validation on `main` to enforce PR checks

---

## Documentation

For a detailed walkthrough of the CI/CD setup, see [CICD_IMPLEMENTATION_GUIDE.md](CICD_IMPLEMENTATION_GUIDE.md).

---

## Cleanup

```bash
databricks bundle destroy -t dev --auto-approve
```

Or use the helper script:

```bash
./scripts/destroy.sh dev
```
