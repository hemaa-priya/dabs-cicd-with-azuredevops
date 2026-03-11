#!/usr/bin/env bash
# =============================================================================
# Local deploy helper — validates and deploys the bundle to a target
# Usage: ./scripts/deploy.sh [dev|staging|prod]
# =============================================================================
set -euo pipefail

TARGET="${1:-dev}"

echo "============================================="
echo " Deploying acc-devops-cicd-demo → ${TARGET}"
echo "============================================="

echo ""
echo "Step 1: Validate bundle..."
databricks bundle validate -t "${TARGET}"

echo ""
echo "Step 2: Deploy bundle..."
databricks bundle deploy -t "${TARGET}" --auto-approve

echo ""
echo "Step 3: Post-deploy — Genie Space..."
if command -v python3 &> /dev/null; then
    python3 scripts/manage_genie_space.py --target "${TARGET}" || echo "Genie Space deploy skipped (set DATABRICKS_TOKEN)"
fi

echo ""
echo "============================================="
echo " Deployment to ${TARGET} complete!"
echo "============================================="
echo ""
echo "To run the ETL job:"
echo "  databricks bundle run etl_orders_job -t ${TARGET}"
echo ""
echo "To run the DLT pipeline:"
echo "  databricks bundle run orders_dlt_pipeline -t ${TARGET}"
