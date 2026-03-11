# CI/CD Guide: DABs + Azure DevOps (Dev → Prod)

---

## The Flow

```
 dev branch (push)  ──────▶  auto-deploy to DEV workspace
 dev → main (PR + merge)  ──▶  auto-deploy to PROD workspace
```

| Branch | Deploys to | Workspace |
|--------|-----------|-----------|
| `dev` | DEV | `adb-7405611575787307` |
| `main` | PROD | `adb-7405607309453399` |

---

## Prerequisites

- Databricks CLI installed locally (`curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`)
- DABs working locally (you've already done this)
- Azure DevOps repo with your code on `main`

---

## Step 1: Create Variable Group in Azure DevOps

The pipeline uses a variable group called `hp_dbr_secrets`. This is where your tokens live.

1. Go to **Pipelines** → **Library**
2. Click **+ Variable group**
3. Name it exactly: `hp_dbr_secrets`
4. Add these 4 variables:

| Variable | Value | Secret? |
|----------|-------|---------|
| `DATABRICKS_HOST_DEV` | `https://adb-7405611575787307.7.azuredatabricks.net` | No |
| `DATABRICKS_HOST_PROD` | `https://adb-7405607309453399.19.azuredatabricks.net` | No |
| `DATABRICKS_TOKEN_DEV` | *(PAT from your dev workspace)* | **Yes** |
| `DATABRICKS_TOKEN_PROD` | *(PAT from your prod workspace)* | **Yes** |

5. Click **Save**

### How to get a PAT

For each workspace:
1. Open the workspace URL
2. Click profile icon (top-right) → **Settings** → **Developer** → **Access tokens**
3. **Generate new token** → copy it

### Authorize the variable group

After saving the variable group:
1. On the variable group page, click the **Pipeline permissions** tab
2. Click **+** → select your pipeline → **Authorize**

Or: the first time the pipeline runs, Azure DevOps will show a **"Permit"** button — click it.

---

## Step 2: Create the Pipeline

1. Go to **Pipelines** → **New Pipeline**
2. Select **Azure Repos Git** → select your repo
3. Choose **Existing Azure Pipelines YAML file**
4. Path: `.azure-devops/azure-pipelines.yml`
5. Click **Save** (not "Save and run" — you'll trigger it via a push)

---

## Step 3: Create dev Branch and Push

```bash
cd /Users/hemapriya.nagarajan/Desktop/work/acc_devops

git checkout main
git pull origin main

# Create dev branch
git checkout -b dev

# Push it (this triggers the pipeline → deploys to DEV workspace)
git push -u origin dev
```

Go to **Pipelines** in Azure DevOps — you'll see the "Deploy to DEV" stage running.

---

## Step 4: Develop on dev Branch

This is your daily workflow:

```bash
git checkout dev

# Make changes (edit notebooks, add jobs, update configs)
# ...

git add .
git commit -m "Add new gold metric"
git push origin dev
```

Every push to `dev` automatically deploys to your DEV workspace.

---

## Step 5: Promote to Production

When you're happy with your changes in dev:

1. Go to **Repos** → **Pull Requests** → **New Pull Request**
2. Source: `dev` → Target: `main`
3. Add a title, create the PR
4. Get it approved (or approve it yourself for demo)
5. Click **Complete** → **Complete merge**

This merges `dev` into `main` → pipeline triggers → deploys to PROD workspace.

---

## Step 6: Verify

**DEV workspace** (`adb-7405611575787307`):
- Workflows → `[dev] ETL Orders Pipeline`
- Pipelines → `[dev] Orders DLT Pipeline`

**PROD workspace** (`adb-7405607309453399`):
- Workflows → `[prod] ETL Orders Pipeline`
- Pipelines → `[prod] Orders DLT Pipeline`

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| **Variable group not found / not authorized** | Create `hp_dbr_secrets` in Pipelines → Library (Step 1). Then authorize it for the pipeline. |
| **401 / authentication failed** | PAT expired or wrong. Regenerate and update in the variable group. |
| **bundle validate failed** | Run `databricks bundle validate -t dev` locally to see the actual error. |
| **run_as service principal not found** | Check that `hp_az_sp` exists in the prod workspace. Or comment out `run_as` in databricks.yml. |
| **Pipeline doesn't trigger** | Check branch name is exactly `dev` or `main`. Check pipeline trigger settings. |
