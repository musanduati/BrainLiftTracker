#!/bin/bash

# Load environment variables from existing setup
source .env.aws

# Create new ECR repository for workflowy
ECR_REPOSITORY="workflowy-processor"
ECR_URI_WORKFLOWY="$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPOSITORY"

# Create ECR repository if it doesn't exist
aws ecr create-repository --repository-name $ECR_REPOSITORY --region us-east-1 2>/dev/null || echo "Repository $ECR_REPOSITORY already exists"

# Copy workflowy directory
cp -r ../workflowy .
cp ../requirements.txt .

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI_WORKFLOWY

# Build Docker image
echo "🔨 Building Workflowy processor Docker image..."
docker buildx build --platform linux/amd64 -t workflowy-processor .

# Tag for ECR
docker tag workflowy-processor:latest $ECR_URI_WORKFLOWY:latest

# Push to ECR
echo "📤 Pushing to ECR..."
docker push $ECR_URI_WORKFLOWY:latest

# Cleanup
rm -rf workflowy requirements.txt

echo "✅ Workflowy Docker image pushed to ECR: $ECR_URI_WORKFLOWY:latest"
