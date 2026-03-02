#!/usr/bin/env python
"""
PyPI Upload Script for llm-chat

This script automates the process of building and uploading
the package to PyPI (or TestPyPI for testing).

Usage:
    python scripts/upload_pypi.py          # Upload to PyPI
    python scripts/upload_pypi.py --test   # Upload to TestPyPI first
    python scripts/upload_pypi.py --check  # Just build and check, no upload

Requirements:
    pip install build twine

Environment:
    PYPI_TOKEN - API token for PyPI (or use ~/.pypirc)
    TEST_PYPI_TOKEN - API token for TestPyPI
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_version() -> str:
    """Read version from _version.py."""
    version_file = Path(__file__).parent.parent / "src" / "llm_chat" / "_version.py"
    with open(version_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    raise RuntimeError("Version not found")


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and print output."""
    print(f"\n> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(1)
    return result


def clean_dist() -> None:
    """Clean dist directory."""
    dist_dir = Path(__file__).parent.parent / "dist"
    if dist_dir.exists():
        print(f"Cleaning {dist_dir}...")
        shutil.rmtree(dist_dir)


def build_package() -> None:
    """Build the package."""
    print("\n=== Building package ===")
    project_dir = Path(__file__).parent.parent
    run_command([sys.executable, "-m", "build", str(project_dir)])


def check_package() -> None:
    """Check the built package with twine."""
    print("\n=== Checking package ===")
    dist_dir = Path(__file__).parent.parent / "dist"
    run_command([sys.executable, "-m", "twine", "check", str(dist_dir / "*")])


def upload_to_testpypi() -> None:
    """Upload to TestPyPI."""
    print("\n=== Uploading to TestPyPI ===")
    dist_dir = Path(__file__).parent.parent / "dist"
    
    token = os.environ.get("TEST_PYPI_TOKEN")
    if token:
        run_command([
            sys.executable, "-m", "twine", "upload",
            "--repository-url", "https://test.pypi.org/legacy/",
            "-u", "__token__", "-p", token,
            str(dist_dir / "*"),
        ])
    else:
        run_command([
            sys.executable, "-m", "twine", "upload",
            "--repository", "testpypi",
            str(dist_dir / "*"),
        ])


def upload_to_pypi() -> None:
    """Upload to PyPI."""
    print("\n=== Uploading to PyPI ===")
    dist_dir = Path(__file__).parent.parent / "dist"
    
    token = os.environ.get("PYPI_TOKEN")
    if token:
        run_command([
            sys.executable, "-m", "twine", "upload",
            "-u", "__token__", "-p", token,
            str(dist_dir / "*"),
        ])
    else:
        run_command([
            sys.executable, "-m", "twine", "upload",
            str(dist_dir / "*"),
        ])


def create_git_tag(version: str) -> None:
    """Create a git tag for the release."""
    print(f"\n=== Creating git tag v{version} ===")
    run_command(["git", "tag", f"v{version}"], check=False)
    print(f"Tag v{version} created (push with: git push origin v{version})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload llm-chat to PyPI")
    parser.add_argument("--test", action="store_true", help="Upload to TestPyPI first")
    parser.add_argument("--check", action="store_true", help="Only build and check, don't upload")
    parser.add_argument("--no-clean", action="store_true", help="Don't clean dist directory")
    parser.add_argument("--tag", action="store_true", help="Create git tag after upload")
    args = parser.parse_args()
    
    version = get_version()
    print(f"Version: {version}")
    
    # Confirm
    if not args.check:
        target = "TestPyPI" if args.test else "PyPI"
        response = input(f"\nUpload v{version} to {target}? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            return 1
    
    # Clean
    if not args.no_clean:
        clean_dist()
    
    # Build
    build_package()
    
    # Check
    check_package()
    
    if args.check:
        print("\n=== Check complete (no upload) ===")
        return 0
    
    # Upload
    if args.test:
        upload_to_testpypi()
        print(f"\n=== Uploaded to TestPyPI ===")
        print(f"Install with: pip install -i https://test.pypi.org/simple/ llm-chat=={version}")
        
        response = input("\nContinue to upload to PyPI? [y/N] ")
        if response.lower() != "y":
            print("Stopped before PyPI upload")
            return 0
    
    upload_to_pypi()
    
    print(f"\n=== Uploaded to PyPI ===")
    print(f"Install with: pip install llm-chat=={version}")
    
    # Tag
    if args.tag:
        create_git_tag(version)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
