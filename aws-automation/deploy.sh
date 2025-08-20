#!/bin/bash

# Twitter Thread Automation - AWS Lambda Deployment Script
# This script creates the Lambda function, EventBridge rule, and all necessary AWS resources

set -e

echo "🚀 Starting Twitter Thread Automation deployment..."

# Configuration
LAMBDA_FUNCTION_NAME="twitter-thread-automation"
EVENTBRIDGE_RULE_NAME="twitter-automation-hourly"
IAM_ROLE_NAME="twitter-automation-lambda-role"
REGION="us-east-1"  # Change this to your preferred region

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo_error "AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

echo_success "AWS CLI configured and credentials verified"

# Get Lightsail IP (you'll need to replace this with your actual Lightsail IP)
echo_warning "Please update the Lightsail IP address in the SSM parameters below!"
read -p "Enter your Lightsail IP address: " LIGHTSAIL_IP
read -p "Enter your API key: " API_KEY

API_URL="http://${LIGHTSAIL_IP}:5555"

# Step 1: Create IAM Role for Lambda
echo_info "Creating IAM role for Lambda..."

TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Create the role (ignore error if it already exists)
aws iam create-role \
    --role-name $IAM_ROLE_NAME \
    --assume-role-policy-document "$TRUST_POLICY" \
    --description "Role for Twitter thread automation Lambda" \
    2>/dev/null || echo_warning "IAM role may already exist"

# Attach policies
aws iam attach-role-policy \
    --role-name $IAM_ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create custom policy for SSM and CloudWatch
CUSTOM_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/twitter-automation/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:twitter-automation-*"
    }
  ]
}'

aws iam put-role-policy \
    --role-name $IAM_ROLE_NAME \
    --policy-name "TwitterAutomationPolicy" \
    --policy-document "$CUSTOM_POLICY"

echo_success "IAM role created and policies attached"

# Step 2: Store configuration in SSM Parameter Store
echo_info "Storing configuration in SSM Parameter Store..."

aws ssm put-parameter \
    --name "/twitter-automation/api-url" \
    --value "$API_URL" \
    --type "String" \
    --overwrite

aws ssm put-parameter \
    --name "/twitter-automation/api-key" \
    --value "$API_KEY" \
    --type "SecureString" \
    --overwrite

aws ssm put-parameter \
    --name "/twitter-automation/max-threads-per-run" \
    --value "10" \
    --type "String" \
    --overwrite

aws ssm put-parameter \
    --name "/twitter-automation/delay-between-threads" \
    --value "5" \
    --type "String" \
    --overwrite

aws ssm put-parameter \
    --name "/twitter-automation/timeout-seconds" \
    --value "300" \
    --type "String" \
    --overwrite

echo_success "Configuration stored in SSM Parameter Store"

# Step 3: Create Lambda deployment package
echo_info "Creating Lambda deployment package..."

# Create temp directory
mkdir -p temp_lambda
cd temp_lambda

# Copy function code
cp ../lambda_function.py .

# Install dependencies
pip install -r ../requirements.txt -t .

# Create ZIP file
zip -r ../lambda_function.zip .

# Clean up temp directory
cd ..
rm -rf temp_lambda

echo_success "Lambda deployment package created"

# Step 4: Create or update Lambda function
echo_info "Creating Lambda function..."

# Get the role ARN
ROLE_ARN=$(aws iam get-role --role-name $IAM_ROLE_NAME --query 'Role.Arn' --output text)

# Wait for role to propagate
echo_info "Waiting for IAM role to propagate..."
sleep 10

# Create Lambda function (or update if it exists)
aws lambda create-function \
    --function-name $LAMBDA_FUNCTION_NAME \
    --runtime python3.9 \
    --role $ROLE_ARN \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://lambda_function.zip \
    --description "Automated Twitter thread posting system" \
    --timeout 300 \
    --memory-size 128 \
    --environment Variables='{
        "PYTHONPATH": "/var/task",
        "AWS_DEFAULT_REGION": "'$REGION'"
    }' \
    --tags Environment=production,Project=twitter-automation \
    2>/dev/null && echo_success "Lambda function created" || {
    
    # Function exists, update it
    echo_info "Function exists, updating code..."
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --zip-file fileb://lambda_function.zip
    
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNCTION_NAME \
        --timeout 300 \
        --memory-size 128
    
    echo_success "Lambda function updated"
}

# Step 5: Create EventBridge rule
echo_info "Creating EventBridge rule for hourly execution..."

aws events put-rule \
    --name $EVENTBRIDGE_RULE_NAME \
    --description "Trigger Twitter thread automation every hour" \
    --schedule-expression "rate(1 hour)" \
    --state ENABLED

echo_success "EventBridge rule created"

# Step 6: Add Lambda permission for EventBridge
echo_info "Adding EventBridge permission to Lambda..."

# Remove existing permission if it exists (ignore error)
aws lambda remove-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id "eventbridge-invoke-permission" \
    2>/dev/null || true

# Add permission
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id "eventbridge-invoke-permission" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:$REGION:$(aws sts get-caller-identity --query Account --output text):rule/$EVENTBRIDGE_RULE_NAME"

echo_success "EventBridge permission added to Lambda"

# Step 7: Add Lambda as target to EventBridge rule
echo_info "Adding Lambda as target to EventBridge rule..."

LAMBDA_ARN=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --query 'Configuration.FunctionArn' --output text)

aws events put-targets \
    --rule $EVENTBRIDGE_RULE_NAME \
    --targets "Id"="1","Arn"="$LAMBDA_ARN"

echo_success "Lambda added as target to EventBridge rule"

# Step 8: Create CloudWatch Dashboard (optional)
echo_info "Creating CloudWatch dashboard..."

DASHBOARD_BODY='{
  "widgets": [
    {
      "type": "metric",
      "x": 0,
      "y": 0,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          [ "TwitterAutomation", "TweetsPosted" ],
          [ ".", "ThreadsProcessed" ],
          [ ".", "TweetFailures" ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "'$REGION'",
        "title": "Twitter Automation Metrics",
        "period": 3600
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 6,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          [ "TwitterAutomation", "AutomationExecutions" ],
          [ ".", "AutomationErrors" ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "'$REGION'",
        "title": "Execution Status",
        "period": 3600
      }
    }
  ]
}'

aws cloudwatch put-dashboard \
    --dashboard-name "TwitterThreadAutomation" \
    --dashboard-body "$DASHBOARD_BODY"

echo_success "CloudWatch dashboard created"

# Cleanup
rm -f lambda_function.zip

echo ""
echo_success "🎉 Twitter Thread Automation deployment completed!"
echo ""
echo_info "Resources created:"
echo "  • Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "  • EventBridge Rule: $EVENTBRIDGE_RULE_NAME"
echo "  • IAM Role: $IAM_ROLE_NAME"
echo "  • CloudWatch Dashboard: TwitterThreadAutomation"
echo ""
echo_info "The automation will run every hour automatically."
echo_info "You can test it manually using:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME output.json"
echo ""
echo_warning "Important: Make sure your Lightsail instance is running and accessible!"
echo_warning "Monitor the CloudWatch logs for the first few executions."