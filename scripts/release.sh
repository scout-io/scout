#!/bin/bash

# Scout Helm Chart Release Script
# This script helps with versioning and releasing the Helm chart

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Scout Helm Chart Release Script${NC}"

# Check if required tools are available
check_tool() {
    local tool=$1
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}❌ $tool is not installed or not in PATH${NC}"
        exit 1
    fi
}

check_tool "helm"
check_tool "git"

echo -e "${GREEN}✅ All required tools are available${NC}"

# Get current version
CURRENT_VERSION=$(grep '^version:' helm-chart/Chart.yaml | awk '{print $2}')
echo -e "${BLUE}📦 Current version: $CURRENT_VERSION${NC}"

# Function to update version
update_version() {
    local new_version=$1
    local chart_file="helm-chart/Chart.yaml"
    
    echo -e "${BLUE}🔄 Updating version to $new_version...${NC}"
    
    # Update Chart.yaml version
    sed -i.bak "s/^version: .*/version: $new_version/" $chart_file
    rm -f ${chart_file}.bak
    
    # Update appVersion if needed
    if [[ $new_version == *"-"* ]]; then
        # If version contains pre-release info, use the base version for appVersion
        app_version=$(echo $new_version | cut -d'-' -f1)
    else
        app_version=$new_version
    fi
    
    sed -i.bak "s/^appVersion: .*/appVersion: \"$app_version\"/" $chart_file
    rm -f ${chart_file}.bak
    
    echo -e "${GREEN}✅ Version updated to $new_version${NC}"
}

# Function to create git tag
create_tag() {
    local version=$1
    
    echo -e "${BLUE}🏷️ Creating git tag v$version...${NC}"
    
    if git tag -l "v$version" | grep -q "v$version"; then
        echo -e "${YELLOW}⚠️ Tag v$version already exists${NC}"
        read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git tag -d "v$version"
            git push origin ":refs/tags/v$version" 2>/dev/null || true
        else
            echo -e "${YELLOW}❌ Tag creation cancelled${NC}"
            return 1
        fi
    fi
    
    git add helm-chart/Chart.yaml
    git commit -m "chore: bump version to $version" || true
    git tag "v$version"
    
    echo -e "${GREEN}✅ Git tag v$version created${NC}"
}

# Function to package chart
package_chart() {
    local version=$1
    
    echo -e "${BLUE}📦 Packaging Helm chart...${NC}"
    
    # Create packages directory if it doesn't exist
    mkdir -p packages
    
    # Package the chart
    helm package helm-chart --destination packages/
    
    echo -e "${GREEN}✅ Chart packaged as packages/scout-$version.tgz${NC}"
}

# Function to validate chart
validate_chart() {
    echo -e "${BLUE}🔍 Validating Helm chart...${NC}"
    
    # Lint the chart
    helm lint helm-chart
    
    # Test the chart
    helm template test-scout helm-chart > /dev/null
    
    echo -e "${GREEN}✅ Chart validation passed${NC}"
}

# Main release process
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 <new-version> [--tag] [--package]${NC}"
    echo -e "${YELLOW}Example: $0 1.0.1 --tag --package${NC}"
    exit 1
fi

NEW_VERSION=$1
TAG_RELEASE=false
PACKAGE_CHART=false

# Parse arguments
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            TAG_RELEASE=true
            shift
            ;;
        --package)
            PACKAGE_CHART=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🎯 Release Configuration:${NC}"
echo -e "  New Version: $NEW_VERSION"
echo -e "  Create Tag: $TAG_RELEASE"
echo -e "  Package Chart: $PACKAGE_CHART"
echo ""

# Validate the chart
validate_chart

# Update version
update_version $NEW_VERSION

# Create git tag if requested
if [ "$TAG_RELEASE" = true ]; then
    create_tag $NEW_VERSION
fi

# Package chart if requested
if [ "$PACKAGE_CHART" = true ]; then
    package_chart $NEW_VERSION
fi

echo -e "${GREEN}🎉 Release process completed!${NC}"
echo -e "${BLUE}📝 Next steps:${NC}"
echo -e "  1. Push changes: git push origin main"
if [ "$TAG_RELEASE" = true ]; then
    echo -e "  2. Push tag: git push origin v$NEW_VERSION"
fi
echo -e "  3. The GitHub Action will automatically publish the chart"
echo -e "  4. Users can install with: helm install scout scout/scout" 