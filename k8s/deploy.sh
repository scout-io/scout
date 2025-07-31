#!/bin/bash

# Scout Kubernetes Deployment Script
# This script deploys Scout to a Kubernetes cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Scout to Kubernetes...${NC}"

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

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to apply manifest and check status
apply_manifest() {
    local file=$1
    local description=$2
    
    echo -e "${YELLOW}📦 Applying $description...${NC}"
    kubectl apply -f "$SCRIPT_DIR/$file"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $description applied successfully${NC}"
    else
        echo -e "${RED}❌ Failed to apply $description${NC}"
        exit 1
    fi
}

# Apply manifests in order
echo -e "${BLUE}📋 Applying manifests in order...${NC}"

apply_manifest "namespace.yaml" "Namespace"
apply_manifest "configmap.yaml" "ConfigMap"
apply_manifest "secret.yaml" "Secret"
apply_manifest "redis.yaml" "Redis"
apply_manifest "backend.yaml" "Backend"
apply_manifest "frontend.yaml" "Frontend"
apply_manifest "nginx-config.yaml" "Nginx ConfigMap"
apply_manifest "nginx.yaml" "Nginx & Ingress"
apply_manifest "prometheus-config.yaml" "Prometheus ConfigMap"
apply_manifest "prometheus.yaml" "Prometheus"
apply_manifest "hpa.yaml" "HorizontalPodAutoscaler"

echo -e "${BLUE}⏳ Waiting for pods to be ready...${NC}"

# Wait for deployments to be ready
kubectl wait --for=condition=available --timeout=300s deployment/scout-redis -n scout
kubectl wait --for=condition=available --timeout=300s deployment/scout-backend -n scout
kubectl wait --for=condition=available --timeout=300s deployment/scout-frontend -n scout
kubectl wait --for=condition=available --timeout=300s deployment/scout-nginx -n scout
kubectl wait --for=condition=available --timeout=300s deployment/scout-prometheus -n scout

echo -e "${GREEN}🎉 Scout deployment completed successfully!${NC}"

# Display access information
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
echo -e "${YELLOW}3. LoadBalancer (if supported by your cluster):${NC}"
echo -e "   Edit k8s/nginx.yaml and change service type to LoadBalancer"
echo -e ""
echo -e "${YELLOW}4. Prometheus:${NC}"
echo -e "   kubectl port-forward -n scout svc/scout-prometheus 9090:9090"
echo -e "   Then visit: http://localhost:9090"

echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo -e "View logs: kubectl logs -f -n scout -l app.kubernetes.io/component=backend"
echo -e "Scale backend: kubectl scale deployment scout-backend --replicas=5 -n scout"
echo -e "Delete deployment: kubectl delete namespace scout"

echo -e "${GREEN}✨ Happy testing with Scout!${NC}" 