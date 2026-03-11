# CI/CD Guide: DABs + Azure DevOps (Dev → Prod)

## The Flow

```
 dev branch (push)  ──────▶  auto-deploy to DEV workspace
 dev → main (PR + merge)  ──▶  auto-deploy to PROD workspace
```

| Branch | Deploys to | Workspace |
|--------|-----------|-----------|
| `dev` | DEV | `adb-7405611575787307` |
| `main` | PROD | `adb-7405607309453399` |

**Auth method:** OAuth M2M with a service principal (not PATs).

---

## Why OAuth over PATs?

| | PAT | OAuth (Service Principal) |
|---|-----|--------------------------|
| Tied to | A person | A service identity |
| Expiry | 90 days max, manual renewal | Long-lived, rotatable secret |
| Audit | Actions logged under the user | Actions logged under the SP |
| Security | If the person leaves, PAT breaks | Independent of any user |
| Best practice | No | **Yes** — Databricks recommended |

---

## Step 1: Create a Service Principal

You need one service principal that has access to **both** workspaces.

### 1a. Create the SP in Databricks Account Console

1. Go to [accounts.azuredatabricks.net](https://accounts.azuredatabricks.net)
2. Click **User management** → **Service principals**
3. Click **Add service principal**
4. Name: `cicd-deployer` (or your preference, you already have `hp_az_sp`)
5. Click **Add**
6. Note the **Application ID** (this is your `DATABRICKS_CLIENT_ID`)

### 1b. Generate an OAuth secret

1. Click on the service principal you just created
2. Go to **Secrets** tab → **Generate secret**
3. Copy the **Secret** value immediately (shown once only) — this is your `DATABRICKS_CLIENT_SECRET`
4. Also note the **Client ID** shown on this page

### 1c. Grant the SP access to both workspaces

For **each** workspace (DEV and PROD):

1. Open the workspace
2. Go to **Settings** → **Identity and access** → **Service principals**
3. Click **Add service principal** → search for `cicd-deployer` (or `hp_az_sp`)
4. Add it
5. Grant it the necessary permissions:
   - **Workspace access**: enabled
   - For prod, if using Unity Catalog: grant `USE CATALOG` and `USE SCHEMA` on the prod catalog/schema
   - For jobs/pipelines: the SP needs permission to create and manage workflows

### 1d. Verify the SP can authenticate

Test locally:

```bash
# Test DEV
DATABRICKS_HOST=https://adb-7405611575787307.7.azuredatabricks.net \
DATABRICKS_CLIENT_ID=<your-client-id> \
DATABRICKS_CLIENT_SECRET=<your-client-secret> \
databricks bundle validate -t dev

# Test PROD
DATABRICKS_HOST=https://adb-7405607309453399.19.azuredatabricks.net \
DATABRICKS_CLIENT_ID=<your-client-id> \
DATABRICKS_CLIENT_SECRET=<your-client-secret> \
databricks bundle validate -t prod
```

If both return successfully, the SP is configured correctly.

---

## Step 2: Create Variable Group in Azure DevOps

1. Go to **Pipelines** → **Library** → **+ Variable group**
2. Name: `hp_dbr_secrets`
3. Add these 4 variables:

| Variable | Value | Secret? |
|----------|-------|---------|
| `DATABRICKS_HOST_DEV` | `https://adb-7405611575787307.7.azuredatabricks.net` | No |
| `DATABRICKS_HOST_PROD` | `https://adb-7405607309453399.19.azuredatabricks.net` | No |
| `DATABRICKS_CLIENT_ID` | *(SP application/client ID from Step 1b)* | **Yes** |
| `DATABRICKS_CLIENT_SECRET` | *(SP OAuth secret from Step 1b)* | **Yes** |

4. Click **Save**
5. Go to **Pipeline permissions** tab → click **+** → authorize your pipeline

> The same `CLIENT_ID` and `CLIENT_SECRET` work for both workspaces because the SP has access to both.

---

## Step 3: Create the Pipeline

1. **Pipelines** → **New Pipeline**
2. **Azure Repos Git** → select your repo
3. **Existing Azure Pipelines YAML file** → path: `.azure-devops/azure-pipelines.yml`
4. Click **Save**

---

## Step 4: Create dev Branch and Push

```bash
cd /Users/hemapriya.nagarajan/Desktop/work/acc_devops

git checkout main
git pull origin main
git checkout -b dev
git push -u origin dev
```

This triggers the pipeline → deploys to DEV workspace.

---

## Step 5: Daily Development

```bash
git checkout dev

# make changes...

git add .
git commit -m "Add new metric"
git push origin dev
# → auto-deploys to DEV workspace
```

---

## Step 6: Promote to Production

1. **Repos** → **Pull Requests** → **New Pull Request**
2. Source: `dev` → Target: `main`
3. Approve and merge
4. Pipeline auto-deploys to PROD workspace

---

## Step 7: Verify

**DEV workspace** → Workflows → `[dev] ETL Orders Pipeline`

**PROD workspace** → Workflows → `[prod] ETL Orders Pipeline`

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| **Variable group not found / not authorized** | Create `hp_dbr_secrets` in Pipelines → Library (Step 2). Authorize it for the pipeline in the Pipeline permissions tab. |
| **401 / Invalid client credentials** | Wrong `CLIENT_ID` or `CLIENT_SECRET`. Regenerate the secret in Account Console. |
| **SP does not have access to workspace** | Add the SP to the workspace (Step 1c). |
| **Permission denied on catalog/schema** | Grant the SP `USE CATALOG` and `USE SCHEMA` in SQL editor: `GRANT USE CATALOG ON CATALOG hp_prod TO \`cicd-deployer\`;` |
| **run_as service principal not found** | The `service_principal_name` in databricks.yml must match the SP name in the workspace. |
| **bundle validate failed** | Test locally with the env vars (Step 1d). |
| **Pipeline doesn't trigger** | Check branch name is exactly `dev` or `main`. |
