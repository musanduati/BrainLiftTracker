#!/bin/bash

set -e

# Add environment parameter
ENVIRONMENT=${1:-test}  # Default to test for safety

echo "🔨 Building and pushing Twitter Automation Docker image for environment: $ENVIRONMENT"

# Check for .env.aws file - FAIL FAST
if [ ! -f .env.aws ]; then
    echo ""
    echo "❌ .env.aws file not found!"
    echo ""
    echo "Docker build requires environment configuration for ECR details."
    echo ""
    echo "Please run: ./aws_complete_setup.sh --setup"
    echo ""
    exit 1
fi

# Load environment variables
source .env.aws

# Validate required variables
if [ -z "$ACCOUNT_ID" ] || [ -z "$ECR_URI" ]; then
    echo "❌ Required variables not set in .env.aws (ACCOUNT_ID, ECR_URI)"
    echo "   Delete .env.aws and run: ./aws_complete_setup.sh --setup"
    exit 1
fi

# Environment-specific tagging
case $ENVIRONMENT in
    test)
        IMAGE_TAG="test-$(date -u +%Y%m%d-%H%M%S)"
        LATEST_TAG="test-latest"
        ;;
    prod|production)
        IMAGE_TAG="prod-$(date -u +%Y%m%d-%H%M%S)"  
        LATEST_TAG="prod-latest"
        ;;
    *)
        echo "❌ Invalid environment: $ENVIRONMENT (use 'test' or 'prod')"
        echo ""
        echo "Usage: $0 [test|prod]"
        echo "  test        Build test image (default, safe)"
        echo "  prod        Build production image"
        echo ""
        exit 1
        ;;
esac

echo "✅ Using configuration from .env.aws:"
echo "   Account ID: $ACCOUNT_ID"
echo "   ECR URI: $ECR_URI"
echo "   Environment: $ENVIRONMENT"
echo "   Versioned Tag: $IMAGE_TAG"
echo "   Latest Tag: $LATEST_TAG"
echo ""

# Generate task definitions if they don't exist
if [ ! -f "ecs-task-definition-twitter-test.json" ]; then
    echo "🔧 Task definitions missing, generating them first..."
    sh aws_complete_setup.sh --generate-tasks
    echo ""
fi

# Create auto-approver directory and copy files
mkdir -p auto-approver
cp -r ../auto-approver/* auto-approver/

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI

# Build Docker image
echo "🔨 Building Twitter Automation Docker image..."
docker buildx build --platform linux/amd64 -t twitter-automation:$IMAGE_TAG .

# Tag for ECR with both versioned and environment-latest tags
docker tag twitter-automation:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker tag twitter-automation:$IMAGE_TAG $ECR_URI:$LATEST_TAG

# Push both tags to ECR
echo "📤 Pushing to ECR..."
docker push $ECR_URI:$IMAGE_TAG
docker push $ECR_URI:$LATEST_TAG

# Cleanup
rm -rf auto-approver

echo ""
echo "✅ Twitter Automation Docker images pushed to ECR:"
echo "   Versioned: $ECR_URI:$IMAGE_TAG"
echo "   Latest: $ECR_URI:$LATEST_TAG"
echo ""
echo "🎯 Image isolation:"
if [ "$ENVIRONMENT" = "test" ]; then
    echo "   ✅ Test image - Safe to deploy without affecting production"
    echo "   🚀 Next: ./register-task-definitions.sh && ./aws_complete_setup.sh --test"
else
    echo "   ⚠️  Production image - Review test results before deployment"
    echo "   🚀 Next: Deploy to production when ready"
fi
echo ""
