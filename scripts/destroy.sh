#!/usr/bin/env bash
# =============================================================================
# Tear down all bundle resources from a target environment
# Usage: ./scripts/destroy.sh [dev|staging|prod]
# =============================================================================
set -euo pipefail

TARGET="${1:-dev}"

echo "WARNING: This will destroy all resources in the '${TARGET}' environment!"
read -p "Type 'yes' to confirm: " confirm

if [ "${confirm}" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

databricks bundle destroy -t "${TARGET}" --auto-approve
echo "All resources destroyed in ${TARGET}."
