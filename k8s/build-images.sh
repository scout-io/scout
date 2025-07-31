#!/bin/bash

# Scout Docker Image Build Script
# This script builds the Docker images needed for Kubernetes deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Building Scout Docker Images...${NC}"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is available${NC}"

# Get the directory of the script (should be k8s/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root (parent of k8s/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Function to build image
build_image() {
    local context=$1
    local image_name=$2
    local description=$3
    
    echo -e "${YELLOW}🔨 Building $description...${NC}"
    
    if docker build -t "$image_name:latest" "$context"; then
        echo -e "${GREEN}✅ $description built successfully${NC}"
    else
        echo -e "${RED}❌ Failed to build $description${NC}"
        exit 1
    fi
}

# Build images
echo -e "${BLUE}📋 Building images...${NC}"

build_image "./backend" "scout-backend" "Backend"
build_image "./frontend" "scout-frontend" "Frontend"

echo -e "${GREEN}🎉 All images built successfully!${NC}"

# Show built images
echo -e "${BLUE}📊 Built Images:${NC}"
docker images | grep -E "(scout-backend|scout-frontend)" || echo "No Scout images found"

echo -e "${BLUE}💡 Next Steps:${NC}"
echo -e "1. If using a remote cluster, push images to a registry:"
echo -e "   docker tag scout-backend:latest your-registry/scout-backend:latest"
echo -e "   docker push your-registry/scout-backend:latest"
echo -e "   docker tag scout-frontend:latest your-registry/scout-frontend:latest"
echo -e "   docker push your-registry/scout-frontend:latest"
echo -e ""
echo -e "2. Update image references in k8s/backend.yaml and k8s/frontend.yaml"
echo -e ""
echo -e "3. Deploy to Kubernetes:"
echo -e "   ./k8s/deploy.sh"

echo -e "${GREEN}✨ Images ready for deployment!${NC}" 