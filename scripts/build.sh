#!/bin/bash
# Build script for schema2code package

set -e

echo "Building schema2code package..."

# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Install build dependencies
python -m pip install --upgrade pip build twine

# Build the package
echo "Building wheel and source distribution..."
python -m build

# Check the package
echo "Checking package integrity..."
twine check dist/*

# Show what was built
echo "Built packages:"
ls -la dist/

echo "Build complete!"
echo "To upload to PyPI: twine upload dist/*"