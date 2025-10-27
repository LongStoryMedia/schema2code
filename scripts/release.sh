#!/bin/bash
# Release script for schema2code package

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

VERSION=$1
TAG="v$VERSION"

echo "Preparing release $VERSION..."

# Update version in __version__.py
echo "Updating version to $VERSION..."
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/__version__.py
rm src/__version__.py.bak

# Commit version change
git add src/__version__.py
git commit -m "Bump version to $VERSION"

# Create and push tag
echo "Creating tag $TAG..."
git tag -a "$TAG" -m "Release version $VERSION"

echo "Push changes and tag:"
echo "  git push origin main"
echo "  git push origin $TAG"
echo ""
echo "This will trigger the release workflow on GitHub Actions."