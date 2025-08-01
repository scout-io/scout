#!/bin/bash

# Scout Helm Chart Deployment Script
# This script builds images, loads them into kind, and deploys Scout using Helm

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Scout with Helm...${NC}"

# Check if required tools are available
check_tool() {
    local tool=$1
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}❌ $tool is not installed or not in PATH${NC}"
        exit 1
    fi
}

check_tool "helm"
check_tool "kubectl"
check_tool "docker"

echo -e "${GREEN}✅ All required tools are available${NC}"

# Check if we can connect to the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Connected to Kubernetes cluster${NC}"

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Function to build and load images
build_and_load_images() {
    echo -e "${BLUE}🐳 Building Docker images...${NC}"
    
    # Build images
    docker build -t scout-backend:latest ./backend
    docker build -t scout-frontend:latest ./frontend
    
    echo -e "${GREEN}✅ Images built successfully${NC}"
    
    # Check if we're using kind
    if kubectl config current-context | grep -q "kind"; then
        echo -e "${BLUE}📦 Loading images into kind cluster...${NC}"
        
        # Get kind cluster name from context
        CLUSTER_NAME=$(kubectl config current-context | sed 's/kind-//')
        
        kind load docker-image scout-backend:latest --name $CLUSTER_NAME
        kind load docker-image scout-frontend:latest --name $CLUSTER_NAME
        
        echo -e "${GREEN}✅ Images loaded into kind cluster${NC}"
    else
        echo -e "${YELLOW}⚠️ Not using kind cluster, skipping image loading${NC}"
        echo -e "${YELLOW}Make sure images are available in your cluster's registry${NC}"
    fi
}

# Function to deploy with Helm
deploy_with_helm() {
    local release_name=${1:-scout}
    local values_file=${2:-""}
    
    echo -e "${BLUE}📦 Deploying Scout with Helm...${NC}"
    
    # Check if release already exists
    if helm list -n scout | grep -q $release_name; then
        echo -e "${YELLOW}⚠️ Release $release_name already exists, upgrading...${NC}"
        
        if [ -n "$values_file" ]; then
            helm upgrade $release_name ./helm-chart -f $values_file
        else
            helm upgrade $release_name ./helm-chart
        fi
    else
        echo -e "${BLUE}📦 Installing new release $release_name...${NC}"
        
        if [ -n "$values_file" ]; then
            helm install $release_name ./helm-chart -f $values_file
        else
            helm install $release_name ./helm-chart
        fi
    fi
    
    echo -e "${GREEN}✅ Helm deployment completed${NC}"
}

# Function to wait for deployment
wait_for_deployment() {
    local release_name=${1:-scout}
    
    echo -e "${BLUE}⏳ Waiting for deployment to be ready...${NC}"
    
    # Wait for all deployments to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/scout-redis -n scout
    kubectl wait --for=condition=available --timeout=300s deployment/scout-backend -n scout
    kubectl wait --for=condition=available --timeout=300s deployment/scout-frontend -n scout
    kubectl wait --for=condition=available --timeout=300s deployment/scout-nginx -n scout
    
    if kubectl get deployment scout-prometheus -n scout &> /dev/null; then
        kubectl wait --for=condition=available --timeout=300s deployment/scout-prometheus -n scout
    fi
    
    echo -e "${GREEN}✅ All deployments are ready${NC}"
}

# Function to show deployment status
show_status() {
    echo -e "${BLUE}📊 Deployment Status:${NC}"
    kubectl get pods -n scout
    
    echo -e "${BLUE}🌐 Access Information:${NC}"
    echo -e "To access Scout, you have several options:"
    echo -e ""
    echo -e "${YELLOW}1. Port Forward (for local testing):${NC}"
    echo -e "   kubectl port-forward -n scout svc/scout-nginx 8080:80"
    echo -e "   Then visit: http://localhost:8080"
    echo -e ""
    echo -e "${YELLOW}2. Ingress (if you have an ingress controller):${NC}"
    echo -e "   Add 'scout.local' to your /etc/hosts file pointing to your ingress IP"
    echo -e "   Then visit: http://scout.local"
    echo -e ""
    echo -e "${YELLOW}3. Prometheus:${NC}"
    echo -e "   kubectl port-forward -n scout svc/scout-prometheus 9090:9090"
    echo -e "   Then visit: http://localhost:9090"
    echo -e ""
    echo -e "${BLUE}🔧 Useful Commands:${NC}"
    echo -e "View logs: kubectl logs -f -n scout -l app.kubernetes.io/component=backend"
    echo -e "Scale backend: kubectl scale deployment scout-backend --replicas=5 -n scout"
    echo -e "Upgrade: helm upgrade scout ./helm-chart"
    echo -e "Uninstall: helm uninstall scout"
}

# Parse command line arguments
RELEASE_NAME="scout"
VALUES_FILE=""
BUILD_IMAGES=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        --values)
            VALUES_FILE="$2"
            shift 2
            ;;
        --no-build)
            BUILD_IMAGES=false
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --release-name NAME    Set the Helm release name (default: scout)"
            echo "  --values FILE          Use custom values file"
            echo "  --no-build            Skip building and loading images"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main deployment process
if [ "$BUILD_IMAGES" = true ]; then
    build_and_load_images
fi

deploy_with_helm $RELEASE_NAME $VALUES_FILE
wait_for_deployment $RELEASE_NAME
show_status

echo -e "${GREEN}🎉 Scout deployment completed successfully!${NC}"
echo -e "${GREEN}✨ Happy testing with Scout!${NC}" 