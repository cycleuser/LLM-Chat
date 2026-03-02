#!/bin/bash
# ============================================================
# LLM-Chat PyPI Publish Script for Unix/Linux/macOS
# ============================================================
# Usage:
#   ./publish.sh          - Build and upload to PyPI
#   ./publish.sh test     - Build and upload to TestPyPI
#   ./publish.sh build    - Only build, no upload
#   ./publish.sh check    - Build and check package
#
# Prerequisites:
#   1. Install dev dependencies: uv pip install -e ".[dev]"
#   2. Set PyPI token: export TWINE_PASSWORD=pypi-xxxx
#      Or create ~/.pypirc with credentials
# ============================================================

set -e

MODE="${1:-pypi}"

echo ""
echo "============================================================"
echo " LLM-Chat Package Publisher"
echo "============================================================"
echo ""

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "[ERROR] uv not found. Please install uv first."
    echo "        https://docs.astral.sh/uv/"
    exit 1
fi

# Step 1: Clean old builds
echo "[1/4] Cleaning old build artifacts..."
rm -rf dist/ build/ src/*.egg-info src/llm_chat.egg-info
echo "      Done."
echo ""

# Step 2: Install/update build tools
echo "[2/4] Ensuring build tools are installed..."
uv pip install build twine --quiet
echo "      Done."
echo ""

# Step 3: Build package
echo "[3/4] Building package..."
uv run python -m build
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
        uv run twine check dist/*
        ;;
    test)
        echo "[4/4] Uploading to TestPyPI..."
        echo ""
        echo "NOTE: You need a TestPyPI account and token."
        echo "      Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc"
        echo ""
        uv run twine upload --repository testpypi dist/*
        echo ""
        echo "Success! Package uploaded to TestPyPI."
        echo "Install with: pip install -i https://test.pypi.org/simple/ llm-chat"
        ;;
    pypi|*)
        echo "[4/4] Uploading to PyPI..."
        echo ""
        echo "NOTE: You need a PyPI account and token."
        echo "      Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc"
        echo ""
        uv run twine upload dist/*
        echo ""
        echo "Success! Package uploaded to PyPI."
        echo "Install with: pip install llm-chat"
        ;;
esac

echo ""
echo "============================================================"
echo " Done!"
echo "============================================================"
