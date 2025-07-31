#!/bin/bash

# Scout Kubernetes Cleanup Script
# This script removes Scout from a Kubernetes cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 Cleaning up Scout from Kubernetes...${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
    exit 1
fi

# Check if we can connect to the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Connected to Kubernetes cluster${NC}"

# Check if scout namespace exists
if ! kubectl get namespace scout &> /dev/null; then
    echo -e "${YELLOW}⚠️ Scout namespace does not exist, nothing to clean up${NC}"
    exit 0
fi

# Ask for confirmation
echo -e "${YELLOW}⚠️ This will delete the entire Scout deployment including all data.${NC}"
echo -e "${YELLOW}   This action cannot be undone.${NC}"
echo -e ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo -e "${BLUE}ℹ️ Cleanup cancelled${NC}"
    exit 0
fi

echo -e "${BLUE}🗑️ Removing Scout resources...${NC}"

# Remove cluster-scoped resources first
echo -e "${YELLOW}📦 Removing cluster-scoped resources...${NC}"
kubectl delete clusterrole prometheus --ignore-not-found=true
kubectl delete clusterrolebinding prometheus --ignore-not-found=true

# Remove the namespace (this will delete all namespaced resources)
echo -e "${YELLOW}📦 Removing Scout namespace...${NC}"
kubectl delete namespace scout

echo -e "${GREEN}🎉 Scout cleanup completed successfully!${NC}"

# Show remaining resources (should be none)
echo -e "${BLUE}📊 Verifying cleanup...${NC}"
if kubectl get namespace scout &> /dev/null; then
    echo -e "${YELLOW}⚠️ Namespace still exists (may take a moment to fully delete)${NC}"
else
    echo -e "${GREEN}✅ Namespace successfully removed${NC}"
fi

# Check for any remaining cluster resources
REMAINING_CLUSTER_RESOURCES=$(kubectl get clusterrole,clusterrolebinding | grep prometheus || true)
if [ -n "$REMAINING_CLUSTER_RESOURCES" ]; then
    echo -e "${YELLOW}⚠️ Some cluster resources may still exist:${NC}"
    echo "$REMAINING_CLUSTER_RESOURCES"
else
    echo -e "${GREEN}✅ All cluster resources removed${NC}"
fi

echo -e "${GREEN}✨ Scout has been completely removed from your cluster!${NC}" 