# CI/CD Implementation Guide: DABs + Azure DevOps (Dev → Prod)

Step-by-step guide to set up CI/CD that deploys Databricks Asset Bundles from a **dev workspace** to a **prod workspace** using Azure DevOps Pipelines.

---

## Your Environment

| Item | Value |
|------|-------|
| DEV workspace | `https://adb-7405611575787307.7.azuredatabricks.net` |
| PROD workspace | `https://adb-7405607309453399.19.azuredatabricks.net` |
| Bundle name | `acc-devops-cicd-demo` |
| Azure DevOps pipeline | `.azure-devops/azure-pipelines.yml` |

## How the Flow Works

```
                          Azure DevOps Repo
                          ┌──────────────────┐
                          │                  │
  ┌── dev branch ────────▶│  Push to dev     │──── auto ────▶  Deploy to DEV workspace
  │                       │                  │
  │   PR: dev → main ───▶│  PR Validation   │──── auto ────▶  Validate only (no deploy)
  │                       │                  │
  └── main branch ───────▶│  Merge to main   │── approval ──▶  Deploy to PROD workspace
                          │                  │
                          └──────────────────┘
```

**Branch mapping:**
- `dev` branch → deploys to **DEV** workspace (`-t dev`)
- `main` branch → deploys to **PROD** workspace (`-t prod`)
- PR to `main` → validates both targets, does **not** deploy

---

## Step 1: Generate Personal Access Tokens

You need a PAT for each workspace so Azure DevOps can authenticate.

### 1a. DEV workspace PAT

1. Go to your DEV workspace: `https://adb-7405611575787307.7.azuredatabricks.net`
2. Click your profile icon (top-right) → **Settings**
3. Go to **Developer** → **Access tokens**
4. Click **Generate new token**
5. Name: `azure-devops-cicd-dev`
6. Lifetime: 90 days (or as needed)
7. Click **Generate** → **copy the token immediately** (you can't see it again)

### 1b. PROD workspace PAT

1. Go to your PROD workspace: `https://adb-7405607309453399.19.azuredatabricks.net`
2. Repeat the same steps
3. Name: `azure-devops-cicd-prod`
4. Copy the token

> **Save both tokens somewhere safe** — you'll add them to Azure DevOps in Step 3.

---

## Step 2: Set Up Git Branches in Azure DevOps

Your code is currently on `main`. You need to create a `dev` branch.

### 2a. Create the dev branch (from your terminal)

```bash
cd /Users/hemapriya.nagarajan/Desktop/work/acc_devops

# Make sure you're on main and it's up to date
git checkout main
git pull origin main

# Create and switch to dev branch
git checkout -b dev

# Push the dev branch to Azure DevOps
git push -u origin dev
```

### 2b. Verify branches in Azure DevOps

1. Go to your Azure DevOps project
2. Navigate to **Repos** → **Branches**
3. You should see both `main` and `dev`

---

## Step 3: Add Secret Variables to the Pipeline

This is what caused your error. The pipeline referenced a **variable group** that didn't exist. The updated pipeline uses inline variables for the hosts, but **tokens must be added as secret variables** in the Azure DevOps UI.

### 3a. Add secret variables (Quick Start — recommended first)

1. Go to **Pipelines** in Azure DevOps
2. Find your pipeline → click **Edit**
3. Click **Variables** (top-right button)
4. Add these variables one by one:

| Name | Value | Keep this value secret? |
|------|-------|------------------------|
| `DATABRICKS_TOKEN_DEV` | *(paste your DEV PAT from Step 1a)* | **Yes** (check the box) |
| `DATABRICKS_TOKEN_PROD` | *(paste your PROD PAT from Step 1b)* | **Yes** (check the box) |

5. Click **Save**

> **Why not use a variable group?** Variable groups require extra authorization steps. Start with pipeline-level secret variables — they just work. You can migrate to a variable group later (see Appendix A).

### 3b. Verify the pipeline YAML has inline host variables

Open `.azure-devops/azure-pipelines.yml` and confirm the `variables:` section has your workspace URLs:

```yaml
variables:
  DATABRICKS_HOST_DEV: "https://adb-7405611575787307.7.azuredatabricks.net"
  DATABRICKS_HOST_PROD: "https://adb-7405607309453399.19.azuredatabricks.net"
```

These are already set in the updated pipeline file.

---

## Step 4: Create the Pipeline in Azure DevOps

If you haven't created the pipeline yet, or want to recreate it:

1. Go to **Pipelines** → **New Pipeline**
2. Select **Azure Repos Git**
3. Select your repository
4. Choose **Existing Azure Pipelines YAML file**
5. Branch: `main`
6. Path: `.azure-devops/azure-pipelines.yml`
7. Click **Continue**
8. **Don't click Run yet** — first click **Variables** and add the secrets from Step 3a
9. Click **Save** (not "Save and run")

---

## Step 5: Fix the Prod Target in databricks.yml

Before deploying to prod, you need valid values in the prod target. Your current `databricks.yml` has placeholders.

Open `databricks.yml` and update the `prod` target:

```yaml
  prod:
    mode: production
    workspace:
      host: https://adb-7405607309453399.19.azuredatabricks.net
    variables:
      catalog: "<YOUR_PROD_CATALOG>"       # e.g., "prod_catalog" or same as dev
      schema: "<YOUR_PROD_SCHEMA>"         # e.g., "prod_schema"
      warehouse_id: "<YOUR_PROD_WAREHOUSE_ID>"  # Get from prod workspace
      node_type: "Standard_DS3_v2"
```

**To find your PROD warehouse ID:**
1. Go to your PROD workspace
2. Navigate to **SQL Warehouses**
3. Click on a warehouse → the ID is in the URL or in the details panel

**If you don't have a separate catalog/schema in prod yet**, you can temporarily use the same values as dev or create new ones:
```sql
-- Run in your PROD workspace SQL editor:
CREATE CATALOG IF NOT EXISTS prod_catalog;
CREATE SCHEMA IF NOT EXISTS prod_catalog.prod_schema;
```

**Important:** Also remove or update the `run_as` section if you don't have a service principal yet:
```yaml
  prod:
    mode: production
    workspace:
      host: https://adb-7405607309453399.19.azuredatabricks.net
    # Remove run_as if you don't have a service principal:
    # run_as:
    #   service_principal_name: "cicd-service-principal"
    variables:
      catalog: "prod_catalog"
      schema: "prod_schema"
      warehouse_id: "your-actual-warehouse-id"
      node_type: "Standard_DS3_v2"
```

---

## Step 6: Test — Deploy to DEV via Pipeline

Now let's trigger the pipeline for the dev branch.

### 6a. Make a change on the dev branch and push

```bash
# Switch to dev branch
git checkout dev

# Make any small change (e.g., edit a notebook comment)
# Or just commit the updated pipeline and databricks.yml:
git add .
git commit -m "Configure CI/CD pipeline with dev and prod targets"
git push origin dev
```

### 6b. Watch the pipeline run

1. Go to **Pipelines** in Azure DevOps
2. You should see a new run triggered by the push to `dev`
3. It will run the **"Deploy to DEV"** stage
4. Click into it to see the logs for each step:
   - Install Databricks CLI
   - Validate (dev)
   - Deploy (dev)
   - Summary

### 6c. Verify in DEV workspace

1. Go to `https://adb-7405611575787307.7.azuredatabricks.net`
2. Navigate to **Workflows** → you should see `[dev] ETL Orders Pipeline`
3. Navigate to **Compute** → **Pipelines** → you should see `[dev] Orders DLT Pipeline`

---

## Step 7: Promote to PROD via Pull Request

### 7a. Create a Pull Request: dev → main

```bash
# Option 1: From terminal
# (make sure all your changes are committed and pushed to dev)
git checkout dev
git push origin dev
```

Then in Azure DevOps:
1. Go to **Repos** → **Pull Requests** → **New Pull Request**
2. Source branch: `dev`
3. Target branch: `main`
4. Title: "Deploy orders pipeline to production"
5. Click **Create**

### 7b. PR Validation runs automatically

The pipeline will trigger the **Validate** stage:
- Validates `databricks bundle validate -t dev`
- Validates `databricks bundle validate -t prod`
- If validation fails, you'll see the errors in the PR

### 7c. Approve and merge the PR

1. Once validation passes, approve the PR
2. Click **Complete** → **Complete merge**
3. This merges `dev` into `main`

### 7d. Production deployment triggers

After the merge to `main`:
1. The pipeline triggers the **"Deploy to PROD"** stage
2. If you set up an approval gate on the `databricks-production` environment (see Step 8), it will wait for approval
3. If no approval gate, it deploys directly

### 7e. Verify in PROD workspace

1. Go to `https://adb-7405607309453399.19.azuredatabricks.net`
2. Navigate to **Workflows** → you should see `[prod] ETL Orders Pipeline`
3. The notebooks, jobs, and pipeline definitions are now in production

---

## Step 8: (Optional) Add Approval Gate for Prod

To require manual approval before deploying to production:

1. Go to **Pipelines** → **Environments**
2. Click **databricks-production** (it gets auto-created on first run)
   - If it doesn't exist yet, click **New environment**, name it `databricks-production`
3. Click the **⋮** (three dots) → **Approvals and checks**
4. Click **+ Add check** → **Approvals**
5. Add yourself (or your team) as an approver
6. Click **Create**

Now when code merges to `main`, the pipeline will pause at the prod stage and wait for your approval.

---

## Step 9: Ongoing Development Workflow

After initial setup, your daily workflow looks like this:

```
1. Work on dev branch
   git checkout dev
   # make changes to notebooks, jobs, configs
   git add .
   git commit -m "Add new metric to gold layer"
   git push origin dev
   └── Pipeline auto-deploys to DEV workspace

2. Test in DEV workspace
   - Run the job manually or wait for schedule
   - Verify results look correct

3. Promote to production
   - Create PR: dev → main
   - Pipeline validates both targets
   - Approve and merge
   - Pipeline deploys to PROD workspace (with optional approval gate)

4. Iterate
   git checkout dev
   # continue working...
```

---

## Troubleshooting

### Error: "Variable group was not found or is not authorized"

**Cause:** The pipeline YAML references `- group: databricks-cicd-secrets` but the group doesn't exist.

**Fix:** The updated pipeline uses inline variables instead. If you see this error, ensure the `variables:` section does NOT reference a group:

```yaml
# WRONG (causes the error if group doesn't exist):
variables:
  - group: databricks-cicd-secrets

# RIGHT (inline variables + secrets added in the UI):
variables:
  DATABRICKS_HOST_DEV: "https://adb-7405611575787307.7.azuredatabricks.net"
  DATABRICKS_HOST_PROD: "https://adb-7405607309453399.19.azuredatabricks.net"
```

### Error: "authentication required" or 401/403

**Cause:** Token is missing, expired, or incorrect.

**Fix:**
1. Go to pipeline → **Edit** → **Variables**
2. Delete and re-add `DATABRICKS_TOKEN_DEV` and `DATABRICKS_TOKEN_PROD`
3. Make sure they're marked as **secret**
4. Regenerate PATs if they expired

### Error: "bundle validate failed"

**Cause:** Your `databricks.yml` has invalid configuration.

**Fix:** Test locally first:
```bash
DATABRICKS_HOST=https://adb-7405611575787307.7.azuredatabricks.net \
DATABRICKS_TOKEN=<your-dev-pat> \
databricks bundle validate -t dev
```

### Error: "run_as service principal not found"

**Cause:** The `prod` target has `run_as: service_principal_name: "cicd-service-principal"` but that SP doesn't exist.

**Fix:** Either:
- Remove the `run_as` block from the prod target, OR
- Create the service principal in your Databricks account console

### Pipeline doesn't trigger

**Check:**
- Is the branch name exactly `dev` or `main`? (not `develop`, `Dev`, etc.)
- Are the file paths in the trigger matching your changes?
- Go to pipeline → **Edit** → **Triggers** to verify settings

---

## Appendix A: Migrating to Variable Groups (Later)

Once your pipeline works with inline variables, you can migrate to a variable group for better secrets management.

### Create the variable group

1. Go to **Pipelines** → **Library** → **+ Variable group**
2. Name: `databricks-cicd-secrets`
3. Add variables:

| Name | Value | Secret? |
|------|-------|---------|
| `DATABRICKS_HOST_DEV` | `https://adb-7405611575787307.7.azuredatabricks.net` | No |
| `DATABRICKS_HOST_PROD` | `https://adb-7405607309453399.19.azuredatabricks.net` | No |
| `DATABRICKS_TOKEN_DEV` | *(your DEV PAT)* | **Yes** |
| `DATABRICKS_TOKEN_PROD` | *(your PROD PAT)* | **Yes** |

4. Click **Save**

### Authorize the variable group for the pipeline

1. After saving, click **Pipeline permissions** tab on the variable group
2. Click **+** → select your pipeline
3. Click **Authorize**

**Alternatively**, the first time you run the pipeline with a variable group reference, Azure DevOps will show a permission prompt. Click **Permit** to authorize.

### Update the pipeline YAML

```yaml
# Replace inline variables with:
variables:
  - group: databricks-cicd-secrets
```

Commit and push — the pipeline will now use the variable group.

---

## Appendix B: Using Service Principal Auth (Production-Grade)

For production, replace PATs with a service principal + OAuth:

1. **Create a Service Principal** in Databricks Account Console → **Service principals** → **Add**
2. **Generate an OAuth secret** for the SP
3. **Grant workspace access**: In each workspace, add the SP with appropriate permissions
4. **Update pipeline variables:**

| Name | Value |
|------|-------|
| `DATABRICKS_CLIENT_ID` | SP application ID |
| `DATABRICKS_CLIENT_SECRET` | SP OAuth secret |

5. **Update pipeline env blocks:**

```yaml
env:
  DATABRICKS_HOST: $(DATABRICKS_HOST_DEV)
  DATABRICKS_CLIENT_ID: $(DATABRICKS_CLIENT_ID)
  DATABRICKS_CLIENT_SECRET: $(DATABRICKS_CLIENT_SECRET)
```

Reference: [Workload Identity Federation](https://docs.databricks.com/dev-tools/auth/oauth-federation-provider.html)

---

## Appendix C: Quick Command Reference

```bash
# --- Local development ---
databricks bundle validate -t dev          # Check config
databricks bundle deploy -t dev            # Push to dev workspace
databricks bundle run etl_orders_job -t dev # Run a job
databricks bundle destroy -t dev           # Tear down dev resources

# --- Git workflow ---
git checkout dev                           # Switch to dev branch
git add . && git commit -m "my change"     # Commit
git push origin dev                        # Triggers deploy to DEV

git checkout main                          # Switch to main
git merge dev                              # Merge dev into main
git push origin main                       # Triggers deploy to PROD

# --- Or use PR (recommended) ---
# Push to dev, then create PR dev→main in Azure DevOps UI
```
