#!/bin/bash

echo "🏗️ Building Lambda package with organized module structure..."

# Clean previous builds
rm -rf package/
rm -f workflowy-processor.zip

# Create package directory structure
mkdir -p package/workflowy

# Install dependencies
echo "📦 Installing dependencies..."
pip install --target package/ aiohttp boto3 tenacity diff-match-patch python-dotenv

# Copy the main lambda handler to package root (AWS Lambda expects it here)
echo "***** 📄 Copying Lambda handler... *****"
if [ ! -f "workflowy/lambda_handler.py" ]; then
    echo "❌ ERROR: workflowy/lambda_handler.py not found!"
    exit 1
fi
cp workflowy/lambda_handler.py package/

# Copy module directories (excluding scripts and test_data)
echo "***** 📁 Copying module directories... *****"

if [ ! -d "workflowy/core" ]; then
    echo "❌ ERROR: workflowy/core directory not found!"
    exit 1
fi
cp -r workflowy/core package/workflowy/

# Verify scraper subdirectory was copied
if [ ! -d "package/workflowy/core/scraper" ]; then
    echo "❌ ERROR: workflowy/core/scraper subdirectory not found in package!"
    exit 1
fi

# Verify poster subdirectory was copied
if [ ! -d "package/workflowy/core/poster" ]; then
    echo "❌ ERROR: workflowy/core/poster subdirectory not found in package!"
    exit 1
fi

# echo "📁 Poster submodule:"
# ls -la package/workflowy/core/poster/*.py | head -8

# Copy storage module
if [ ! -d "workflowy/storage" ]; then
    echo "❌ ERROR: workflowy/storage directory not found!"
    exit 1
fi
cp -r workflowy/storage package/workflowy/

# Copy config module
if [ ! -d "workflowy/config" ]; then
    echo "❌ ERROR: workflowy/config directory not found!"
    exit 1
fi
cp -r workflowy/config package/workflowy/

# Copy __init__.py files
cp workflowy/__init__.py package/workflowy/

# Remove any __pycache__ directories
find package/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove any .pyc files
find package/ -name "*.pyc" -delete 2>/dev/null || true

# Verify the structure
echo "***** 🔍 Verifying package structure: *****"
echo "===========📁 Main handler:==========="
ls -la package/lambda_handler.py

echo "===========📁 Core module:==========="
ls -la package/workflowy/core/*.py | head -5

echo "===========📁 Scraper submodule:==========="
ls -la package/workflowy/core/scraper/*.py | head -8

echo "===========📁 Poster submodule:==========="
ls -la package/workflowy/core/poster/*.py | head -8

echo "===========📁 Storage module:==========="
ls -la package/workflowy/storage/*.py | head -5

echo "===========📁 Config module:==========="
ls -la package/workflowy/config/*.py

# Create deployment package
cd package/
echo "📦 Creating zip package..."
zip -qr ../workflowy-processor.zip .
cd ..

# Verify the zip contents - show only our project files, not dependencies
echo "📦 Package contents (our project files only):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
unzip -l workflowy-processor.zip | grep -E "(lambda_handler\.py|workflowy/)" | head -50

# Show summary statistics
echo ""
echo "📊 Package statistics:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Total files in package: $(unzip -l workflowy-processor.zip | tail -1 | awk '{print $2}')"
echo "   Project files: $(unzip -l workflowy-processor.zip | grep -E "(lambda_handler\.py|workflowy/)" | wc -l | tr -d ' ')"
echo "   Dependency files: $(unzip -l workflowy-processor.zip | grep -v -E "(lambda_handler\.py|workflowy/)" | grep -E "\.py$|\.so$|\.json$" | wc -l | tr -d ' ')"

echo ""
echo "✅ Package created: workflowy-processor.zip"
echo "📦 Size: $(du -h workflowy-processor.zip | cut -f1)"
echo ""
echo "📌 Note: Scripts and test data are excluded from the Lambda package"
echo "   - Scripts directory is for local utilities only"
echo "   - Test data is not needed in Lambda environment"
echo "   - Scraper and Poster are now modularized into subdirectories"