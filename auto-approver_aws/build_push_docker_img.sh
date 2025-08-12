# Load environment variables
source .env.aws

mkdir -p auto-approver
cp -r ../auto-approver/* auto-approver/

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI

# Build Docker image specifically for x86_64 (AWS Fargate architecture)
echo "🔨 Building Docker image for x86_64 platform..."
docker buildx build --platform linux/amd64 -t twitter-automation .

# Tag for ECR
docker tag twitter-automation:latest $ECR_URI:latest

# Push to ECR
echo "📤 Pushing to ECR..."
docker push $ECR_URI:latest

rm -rf auto-approver

echo "✅ Docker image pushed to ECR: $ECR_URI:latest"
