#!/bin/bash
# deploy_lambda_fixed.sh

echo "🏗️ Building Lambda package with your code..."

# Clean previous builds
rm -rf package/
rm -f workflowy-processor.zip

# Create package directory
mkdir package/

# Install dependencies
echo "📦 Installing dependencies..."
pip install --target package/ aiohttp boto3 tenacity diff-match-patch dotenv

# Copy your code files (they're directly in workflowy/ directory)
echo "📄 Copying code files..."

# Check source files exist first
if [ ! -f "workflowy/aws_storage.py" ]; then
    echo "❌ ERROR: workflowy/aws_storage.py not found!"
    exit 1
fi

if [ ! -f "workflowy/test_workflowy.py" ]; then
    echo "❌ ERROR: workflowy/test_workflowy.py not found!"
    exit 1
fi

if [ ! -f "workflowy/lambda_handler.py" ]; then
    echo "❌ ERROR: workflowy/lambda_handler.py not found!"
    exit 1
fi

if [ ! -f "workflowy/post_tweets.py" ]; then
    echo "❌ ERROR: workflowy/post_tweets.py not found!"
    exit 1
fi

if [ ! -f "workflowy/llm_service.py" ]; then
    echo "❌ ERROR: workflowy/llm_service.py not found!"
    exit 1
fi

# Copy files
cp workflowy/aws_storage.py package/
cp workflowy/test_workflowy.py package/
cp workflowy/lambda_handler.py package/
cp workflowy/post_tweets.py package/
cp workflowy/llm_service.py package/

# Verify files were copied
echo "🔍 Verifying code files in package:"
ls -la package/aws_storage.py package/test_workflowy.py package/lambda_handler.py package/post_tweets.py package/llm_service.py

# Create deployment package
cd package/
zip -r ../workflowy-processor.zip .
cd ..

# Verify the zip contents include your code
echo "📦 Your code files in zip:"
unzip -l workflowy-processor.zip | grep -E "(aws_storage|test_workflowy|lambda_handler|post_tweets|llm_service)\.py"

echo "✅ Package created: workflowy-processor.zip"
echo "📦 Size: $(du -h workflowy-processor.zip | cut -f1)"