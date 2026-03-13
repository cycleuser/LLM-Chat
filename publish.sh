#!/bin/bash
# ============================================================
# Liao PyPI Publish Script for Unix/Linux/macOS
# ============================================================
# Usage:
#   ./publish.sh          - Build and upload to PyPI
#   ./publish.sh test     - Build and upload to TestPyPI
#   ./publish.sh build    - Only build, no upload
#   ./publish.sh check    - Build and check package
#
# Prerequisites:
#   1. Install build tools: pip install build twine
#   2. Set PyPI token: export TWINE_PASSWORD=pypi-xxxx
#      Or create ~/.pypirc with credentials
# ============================================================

set -e

MODE="${1:-pypi}"

echo ""
echo "============================================================"
echo " Liao Package Publisher"
echo "============================================================"
echo ""

# Step 1: Clean old builds
echo "[1/4] Cleaning old build artifacts..."
rm -rf dist/ build/ src/*.egg-info src/liao.egg-info
echo "      Done."
echo ""

# Step 2: Install/update build tools
echo "[2/4] Ensuring build tools are installed..."
pip install build twine --quiet --upgrade
echo "      Done."
echo ""

# Step 3: Build package
echo "[3/4] Building package..."
python -m build
echo "      Done."
echo ""

# Show built files
echo "Built packages:"
ls -la dist/
echo ""

# Step 4: Check or Upload
case "$MODE" in
    build)
        echo "[4/4] Build only mode - skipping upload."
        echo ""
        echo "Build complete! Packages are in dist/"
        ;;
    check)
        echo "[4/4] Checking package with twine..."
        twine check dist/*
        ;;
    test)
        echo "[4/4] Uploading to TestPyPI..."
        echo ""
        echo "NOTE: You need a TestPyPI account and token."
        echo "      Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc"
        echo ""
        twine upload --repository testpypi dist/*
        echo ""
        echo "Success! Package uploaded to TestPyPI."
        echo "Install with: pip install -i https://test.pypi.org/simple/ liao"
        ;;
    pypi|*)
        echo "[4/4] Uploading to PyPI..."
        echo ""
        echo "NOTE: You need a PyPI account and token."
        echo "      Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc"
        echo ""
        twine upload dist/*
        echo ""
        echo "Success! Package uploaded to PyPI."
        echo "Install with: pip install liao"
        ;;
esac

echo ""
echo "============================================================"
echo " Done!"
echo "============================================================"
