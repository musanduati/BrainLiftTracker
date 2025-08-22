#!/bin/bash

set -e

echo "🔨 Building and pushing Workflowy Docker image..."

# Check for .env.aws file - FAIL FAST
if [ ! -f .env.aws ]; then
    echo ""
    echo "❌ .env.aws file not found!"
    echo ""
    echo "Docker build requires environment configuration for ECR details."
    echo ""
    echo "Please run: ./setup-workflowy-complete.sh --setup"
    echo ""
    exit 1
fi

# Load environment variables
source .env.aws

# Validate required variables
if [ -z "$ACCOUNT_ID" ] || [ -z "$ECR_URI_WORKFLOWY_PROCESSOR" ]; then
    echo "❌ Required variables not set in .env.aws (ACCOUNT_ID, ECR_URI_WORKFLOWY_PROCESSOR)"
    echo "   Delete .env.aws and run: ./setup-workflowy-complete.sh --setup"
    exit 1
fi

echo "✅ Using configuration from .env.aws:"
echo "   Account ID: $ACCOUNT_ID"
echo "   ECR URI: $ECR_URI_WORKFLOWY_PROCESSOR"
echo ""

# Generate task definitions if they don't exist
if [ ! -f "ecs-task-definition-workflowy-test.json" ]; then
    echo "🔧 Task definitions missing, generating them first..."
    ./generate-task-definitions.sh
    echo ""
fi

# Copy workflowy directory
cp -r ../workflowy .
cp ../requirements.txt .

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI_WORKFLOWY_PROCESSOR

# Build Docker image
echo "🔨 Building Workflowy processor Docker image..."
docker buildx build --platform linux/amd64 -t workflowy-processor .

# Tag for ECR
docker tag workflowy-processor:latest $ECR_URI_WORKFLOWY_PROCESSOR:latest

# Push to ECR
echo "📤 Pushing to ECR..."
docker push $ECR_URI_WORKFLOWY_PROCESSOR:latest

# Cleanup
rm -rf workflowy requirements.txt

echo "✅ Workflowy Docker image pushed to ECR: $ECR_URI_WORKFLOWY_PROCESSOR:latest"
