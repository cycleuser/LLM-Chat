@echo off
REM ============================================================
REM LLM-Chat PyPI Publish Script for Windows
REM ============================================================
REM Usage:
REM   publish.bat          - Build and upload to PyPI
REM   publish.bat test     - Build and upload to TestPyPI
REM   publish.bat build    - Only build, no upload
REM   publish.bat check    - Build and check package
REM
REM Prerequisites:
REM   1. Install dev dependencies: uv pip install -e ".[dev]"
REM   2. Set PyPI token: set TWINE_PASSWORD=pypi-xxxx
REM      Or create ~/.pypirc with credentials
REM ============================================================

setlocal enabledelayedexpansion

set MODE=%1
if "%MODE%"=="" set MODE=pypi

echo.
echo ============================================================
echo  LLM-Chat Package Publisher
echo ============================================================
echo.

REM Check if uv is available
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv not found. Please install uv first.
    echo         https://docs.astral.sh/uv/
    exit /b 1
)

REM Step 1: Clean old builds
echo [1/4] Cleaning old build artifacts...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist src\*.egg-info rmdir /s /q src\*.egg-info
if exist src\llm_chat.egg-info rmdir /s /q src\llm_chat.egg-info
echo       Done.
echo.

REM Step 2: Install/update build tools
echo [2/4] Ensuring build tools are installed...
uv pip install build twine --quiet
echo       Done.
echo.

REM Step 3: Build package
echo [3/4] Building package...
uv run python -m build
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    exit /b 1
)
echo       Done.
echo.

REM Show built files
echo Built packages:
dir /b dist\
echo.

REM Step 4: Check or Upload
if "%MODE%"=="build" (
    echo [4/4] Build only mode - skipping upload.
    echo.
    echo Build complete! Packages are in dist\
    goto :end
)

if "%MODE%"=="check" (
    echo [4/4] Checking package with twine...
    uv run twine check dist\*
    goto :end
)

if "%MODE%"=="test" (
    echo [4/4] Uploading to TestPyPI...
    echo.
    echo NOTE: You need a TestPyPI account and token.
    echo       Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc
    echo.
    uv run twine upload --repository testpypi dist\*
    if %errorlevel% neq 0 (
        echo [ERROR] Upload failed!
        exit /b 1
    )
    echo.
    echo Success! Package uploaded to TestPyPI.
    echo Install with: pip install -i https://test.pypi.org/simple/ llm-chat
    goto :end
)

REM Default: upload to PyPI
echo [4/4] Uploading to PyPI...
echo.
echo NOTE: You need a PyPI account and token.
echo       Set TWINE_PASSWORD=pypi-xxxx or use ~/.pypirc
echo.
uv run twine upload dist\*
if %errorlevel% neq 0 (
    echo [ERROR] Upload failed!
    exit /b 1
)
echo.
echo Success! Package uploaded to PyPI.
echo Install with: pip install llm-chat

:end
echo.
echo ============================================================
echo  Done!
echo ============================================================
endlocal
