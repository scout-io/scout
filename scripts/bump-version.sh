#!/bin/bash

# Version bump script for Scout Helm chart
# Usage: ./scripts/bump-version.sh [patch|minor|major]

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 [patch|minor|major]"
    echo "  patch: 1.1.1 -> 1.1.2"
    echo "  minor: 1.1.1 -> 1.2.0"
    echo "  major: 1.1.1 -> 2.0.0"
    exit 1
fi

BUMP_TYPE=$1
CHART_FILE="charts/scout/Chart.yaml"

# Get current version
CURRENT_VERSION=$(grep "^version:" "$CHART_FILE" | awk '{print $2}')
echo "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# Calculate new version
case $BUMP_TYPE in
    patch)
        NEW_PATCH=$((PATCH + 1))
        NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"
        ;;
    minor)
        NEW_MINOR=$((MINOR + 1))
        NEW_VERSION="$MAJOR.$NEW_MINOR.0"
        ;;
    major)
        NEW_MAJOR=$((MAJOR + 1))
        NEW_VERSION="$NEW_MAJOR.0.0"
        ;;
    *)
        echo "Invalid bump type: $BUMP_TYPE"
        echo "Valid types: patch, minor, major"
        exit 1
        ;;
esac

echo "New version: $NEW_VERSION"

# Update Chart.yaml
sed -i.bak "s/^version: .*/version: $NEW_VERSION/" "$CHART_FILE"
rm -f "$CHART_FILE.bak"

echo "✅ Updated $CHART_FILE to version $NEW_VERSION"

# Commit and push
echo "📝 Committing version bump..."
git add "$CHART_FILE"
git commit -m "chore: bump chart version to $NEW_VERSION"

# Check if we need to pull first (Chart Releaser might have updated index.yaml)
echo "🔄 Checking for remote changes..."
if git fetch origin main && git rev-list HEAD..origin/main --oneline | grep -q .; then
    echo "⚠️  Remote has changes, pulling first..."
    git pull origin main --no-edit
fi

git push origin main

echo "🚀 Pushed version bump to main branch"
echo "📦 Chart Releaser will create release scout-$NEW_VERSION" 