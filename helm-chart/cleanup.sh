#!/bin/bash

# Scout Helm Chart Cleanup Script
# This script removes all Scout resources deployed via Helm

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 Cleaning up Scout Helm deployment...${NC}"

# Parse command line arguments
RELEASE_NAME=${1:-scout}
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS] [RELEASE_NAME]"
            echo ""
            echo "Options:"
            echo "  --release-name NAME    Set the Helm release name (default: scout)"
            echo "  --force               Skip confirmation prompt"
            echo "  --help                Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Clean up 'scout' release"
            echo "  $0 my-scout           # Clean up 'my-scout' release"
            echo "  $0 --force            # Clean up without confirmation"
            exit 0
            ;;
        *)
            RELEASE_NAME="$1"
            shift
            ;;
    esac
done

# Check if Helm is available
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm is not installed or not in PATH${NC}"
    exit 1
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
    exit 1
fi

# Function to check if release exists
check_release() {
    local release=$1
    if helm list -n scout | grep -q $release; then
        return 0
    else
        return 1
    fi
}

# Function to cleanup release
cleanup_release() {
    local release=$1
    
    echo -e "${BLUE}🗑️ Removing Helm release '$release'...${NC}"
    
    if helm uninstall $release -n scout; then
        echo -e "${GREEN}✅ Helm release '$release' removed successfully${NC}"
    else
        echo -e "${YELLOW}⚠️ Helm release '$release' not found or already removed${NC}"
    fi
}

# Function to cleanup namespace
cleanup_namespace() {
    echo -e "${BLUE}🗑️ Removing Scout namespace...${NC}"
    
    if kubectl get namespace scout &> /dev/null; then
        if kubectl delete namespace scout; then
            echo -e "${GREEN}✅ Scout namespace removed successfully${NC}"
        else
            echo -e "${YELLOW}⚠️ Failed to remove Scout namespace (may be in use)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Scout namespace not found${NC}"
    fi
}

# Function to cleanup cluster resources
cleanup_cluster_resources() {
    echo -e "${BLUE}🗑️ Removing cluster-scoped resources...${NC}"
    
    # Remove Prometheus ClusterRole
    if kubectl get clusterrole scout-prometheus &> /dev/null; then
        kubectl delete clusterrole scout-prometheus
        echo -e "${GREEN}✅ Prometheus ClusterRole removed${NC}"
    else
        echo -e "${YELLOW}⚠️ Prometheus ClusterRole not found${NC}"
    fi
    
    # Remove Prometheus ClusterRoleBinding
    if kubectl get clusterrolebinding scout-prometheus &> /dev/null; then
        kubectl delete clusterrolebinding scout-prometheus
        echo -e "${GREEN}✅ Prometheus ClusterRoleBinding removed${NC}"
    else
        echo -e "${YELLOW}⚠️ Prometheus ClusterRoleBinding not found${NC}"
    fi
}

# Function to cleanup persistent volumes
cleanup_persistent_volumes() {
    echo -e "${BLUE}🗑️ Checking for persistent volumes...${NC}"
    
    # List PVCs in scout namespace (if namespace still exists)
    if kubectl get namespace scout &> /dev/null; then
        local pvcs=$(kubectl get pvc -n scout -o name 2>/dev/null || true)
        if [ -n "$pvcs" ]; then
            echo -e "${YELLOW}⚠️ Found persistent volume claims:${NC}"
            echo "$pvcs"
            echo -e "${YELLOW}⚠️ These will be automatically cleaned up when the namespace is removed${NC}"
        else
            echo -e "${GREEN}✅ No persistent volume claims found${NC}"
        fi
    fi
}

# Main cleanup process
if [ "$FORCE" = false ]; then
    echo -e "${YELLOW}⚠️ This will remove ALL Scout resources including:${NC}"
    echo -e "   - Helm release '$RELEASE_NAME'"
    echo -e "   - Scout namespace"
    echo -e "   - All deployments, services, and configs"
    echo -e "   - Persistent volumes (data will be lost!)"
    echo -e "   - Cluster-scoped resources (Prometheus RBAC)"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}❌ Cleanup cancelled${NC}"
        exit 0
    fi
fi

# Check if release exists
if check_release $RELEASE_NAME; then
    echo -e "${GREEN}✅ Found Helm release '$RELEASE_NAME'${NC}"
else
    echo -e "${YELLOW}⚠️ Helm release '$RELEASE_NAME' not found${NC}"
fi

# Perform cleanup
cleanup_release $RELEASE_NAME
cleanup_namespace
cleanup_cluster_resources
cleanup_persistent_volumes

echo -e "${GREEN}🎉 Scout cleanup completed!${NC}"
echo -e "${BLUE}📝 Note: If you had persistent volumes, the data has been permanently deleted${NC}" 