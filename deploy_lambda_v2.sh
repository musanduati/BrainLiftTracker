#!/bin/bash

echo "🏗️ Building Lambda V2 package with your code..."

# Clean previous builds
rm -rf package/
rm -f workflowy-processor-v2.zip

# Create package directory
mkdir package/

# Install dependencies
echo "📦 Installing dependencies..."
pip install --target package/ aiohttp boto3 tenacity diff-match-patch dotenv

# Copy your code files (they're directly in workflowy/ directory)
echo "📄 Copying code files..."

# Check source files exist first
if [ ! -f "workflowy/aws_storage_v2.py" ]; then
    echo "❌ ERROR: workflowy/aws_storage_v2.py not found!"
    exit 1
fi

if [ ! -f "workflowy/test_workflowy_v2.py" ]; then
    echo "❌ ERROR: workflowy/test_workflowy_v2.py not found!"
    exit 1
fi

if [ ! -f "workflowy/lambda_handler_v2.py" ]; then
    echo "❌ ERROR: workflowy/lambda_handler_v2.py not found!"
    exit 1
fi

if [ ! -f "workflowy/post_tweets_v2.py" ]; then
    echo "❌ ERROR: workflowy/post_tweets_v2.py not found!"
    exit 1
fi

if [ ! -f "workflowy/llm_service.py" ]; then
    echo "❌ ERROR: workflowy/llm_service.py not found!"
    exit 1
fi

if [ ! -f "workflowy/bulk_url_processor_v2.py" ]; then
    echo "❌ ERROR: workflowy/bulk_url_processor_v2.py not found!"
    exit 1
fi

if [ ! -f "workflowy/schema_definitions.py" ]; then
    echo "❌ ERROR: workflowy/schema_definitions.py not found!"
    exit 1
fi

if [ ! -f "workflowy/project_id_utils.py" ]; then
    echo "❌ ERROR: workflowy/project_id_utils.py not found!"
    exit 1
fi

# Copy files
cp workflowy/aws_storage_v2.py package/
cp workflowy/test_workflowy_v2.py package/
cp workflowy/lambda_handler_v2.py package/
cp workflowy/post_tweets_v2.py package/
cp workflowy/llm_service.py package/
cp workflowy/logger_config.py package/
cp workflowy/bulk_url_processor_v2.py package/
cp workflowy/schema_definitions.py package/
cp workflowy/project_id_utils.py package/

# Verify files were copied
echo "🔍 Verifying code files in package:"
ls -la package/aws_storage_v2.py package/test_workflowy_v2.py package/lambda_handler_v2.py package/post_tweets_v2.py package/llm_service.py package/logger_config.py package/bulk_url_processor_v2.py package/schema_definitions.py package/project_id_utils.py

# Create deployment package
cd package/
zip -r ../workflowy-processor-v2.zip .
cd ..

# Verify the zip contents include your code
echo "📦 Your code files in zip:"
unzip -l workflowy-processor-v2.zip | grep -E "(aws_storage_v2|test_workflowy_v2|lambda_handler_v2|post_tweets_v2|llm_service|logger_config|bulk_url_processor_v2|schema_definitions|project_id_utils)\.py"

echo "✅ Package created: workflowy-processor-v2.zip"
echo "📦 Size: $(du -h workflowy-processor-v2.zip | cut -f1)"