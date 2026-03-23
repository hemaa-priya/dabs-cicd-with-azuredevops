# Genie Space CI/CD Deployment

This folder contains a custom deployment solution using the Genie REST API.

## How It Works

Genie Spaces are managed separately from DABs resources (jobs, pipelines, notebooks). The `deploy.py` script handles exporting space definitions from a workspace, parameterizing catalog/schema references, and deploying them to other environments.

```
genie/
├── deploy.py                # Export and deploy script (REST API)
├── config.json              # Per-target host, catalog, schema, warehouse
├── deployed_spaces.json     # Tracks deployed space IDs per environment
└── spaces/
    ├──*.json
```

### Key Files

| File | Purpose | Updated by |
|------|---------|------------|
| `config.json` | Workspace URLs, catalog/schema, warehouse IDs per target | You (manually) |
| `deployed_spaces.json` | Maps space names to workspace-specific IDs | `deploy.py` (automatically) |
| `spaces/*.json` | Space definitions with `{{catalog}}`/`{{schema}}` placeholders | `deploy.py --export` |


## Authentication

`deploy.py` checks for credentials in this order:

| Priority | Method | Used by |
|----------|--------|---------|
| 1 | `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` (OAuth M2M) | CI/CD pipeline |
| 2 | `DATABRICKS_TOKEN` (PAT) | Manual override |
| 3 | Databricks CLI (`databricks auth token --host`) | Local development |

For local use, make sure your CLI profiles are valid:

```bash
databricks auth login --host https://adb-<DEV>.azuredatabricks.net
databricks auth login --host https://adb-<PROD>.azuredatabricks.net
```

## CLI Commands

### Export a single space from dev

```bash
python3 genie/deploy.py --target dev --export weather_genie
```

### Export all spaces from dev

```bash
python3 genie/deploy.py --target dev --export-all
```

### Deploy all spaces to prod

```bash
python3 genie/deploy.py --target prod
```

### Deploy all spaces to dev

```bash
python3 genie/deploy.py --target dev
```

## Adding a New Genie Space

1. Create the Genie Space in the **dev workspace UI**
2. Copy the space ID from the URL: `/explore/genie/rooms/<SPACE_ID>`
3. Add the ID to `deployed_spaces.json` under `dev`:

```json
{
  "dev": {
    "my_new_space": "<SPACE_ID>"
  }
}
```

4. Commit and push to `dev` branch
5. The pipeline will:
   - Export the space definition (creates `genie/spaces/my_new_space.json`)
   - Commit it back to `dev`
6. Merge `dev` → `main`
7. The pipeline will:
   - Deploy `my_new_space` to prod
   - Commit the prod space ID back to `main`

### Important: First Prod Deploy Creates Duplicates

The first time a new space is deployed to prod, there is no prod ID in `deployed_spaces.json`, so the script creates a new space. The pipeline attempts to commit the new ID back to `main`, but this requires the Azure DevOps build service account to have **Contribute** permission on the repo.

**If the commit-back fails** (or the pipeline runs again before the commit is merged), a duplicate space is created in prod.

**To prevent duplicates**, after the first prod deploy of a new space:

1. Open the new space in the prod workspace and copy the space ID from the URL
2. Add it manually to `deployed_spaces.json` under `prod`:

```json
{
  "prod": {
    "my_new_space": "<SPACE_ID_FROM_PROD_URL>"
  }
}
```

3. Commit and push to `main`

All subsequent CI/CD runs will update (PATCH) instead of creating duplicates.

**To enable automatic commit-back** (so you don't have to do this manually):
- Azure DevOps → Project Settings → Repos → Security → `<Project> Build Service` → set **Contribute** to **Allow**

## Updating an Existing Genie Space

1. Edit the space in the **dev workspace UI**
2. Push any change to `dev` branch (triggers the pipeline)
3. The pipeline exports the latest definition and commits it
4. Merge `dev` → `main`
5. The pipeline deploys the update to prod

## What Migrates vs What Doesn't

| Migrates | Does NOT migrate |
|----------|------------------|
| Title, description | User/group permissions (CAN VIEW, CAN EDIT) |
| Table references (catalog/schema swapped) | Warehouse permissions |
| Column configurations | Unity Catalog grants |
| Join specifications | Conversation history |
| Instructions / sample questions | |

Permissions must be set separately in each workspace after deployment.

## Parameterization

Space definitions in `genie/spaces/*.json` use placeholders:

- `{{catalog}}` → replaced with target catalog (e.g., `hp_dev` or `hp_prod`)
- `{{schema}}` → replaced with target schema (e.g., `hp_pp_schema` or `prod_schema`)

This allows the same space definition to work across environments pointing at different Unity Catalog locations.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `No space definitions found` | `genie/spaces/` is empty | Run `--export-all` or add space ID to `deployed_spaces.json` and push to dev |
| `FAILED (404)` on PATCH | Space was deleted from workspace UI | Remove the ID from `deployed_spaces.json`, push, and let the pipeline recreate it |
| `FAILED (401)` | Token expired or SP lacks workspace access | Re-login (`databricks auth login`) or check SP permissions |
| Duplicate spaces in prod | `deployed_spaces.json` missing prod ID | The pipeline auto-commits prod IDs now; check if the commit step succeeded |
| Export returns empty | SP needs CAN EDIT on the Genie Space | Grant the SP edit permission on the space in the dev workspace |
