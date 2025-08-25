#!/bin/bash

# ============================================================================
# AWS Twitter Automation Complete Setup Script
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    printf "${BLUE}ℹ️  %s${NC}\n" "$1"
}

log_success() {
    printf "${GREEN}✅ %s${NC}\n" "$1"
}

log_warning() {
    printf "${YELLOW}⚠️  %s${NC}\n" "$1"
}

log_error() {
    printf "${RED}❌ %s${NC}\n" "$1"
}

log_step() {
    printf "\n${BLUE}==== %s ====${NC}\n" "$1"
}

# Help function
show_help() {
    echo "AWS Twitter Automation Setup Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --setup, -s      Run full AWS infrastructure setup"
    echo "  --test, -t       Run test task only (requires existing setup)"
    echo "  --verify, -v     Verify existing setup (default behavior)"
    echo "  --generate-tasks, -g      Generate task definition files from templates"
    echo "  --help, -h       Show this help message"
    echo
    echo "Default behavior: Verify existing AWS setup"
    echo
    echo "Examples:"
    echo "  $0                    # Verify existing setup (default)"
    echo "  $0 --setup          # Run complete infrastructure setup"
    echo "  $0 --test           # Run test task to verify functionality"
    echo "  $0 --verify         # Explicitly verify setup"
    echo "  $0 --generate-tasks      # Generate task definition files"
}

# Error handling
handle_error() {
    log_error "Operation failed at step: $1"
    log_error "Please check the error messages above and resolve the issue."
    exit 1
}

# Check if AWS CLI is configured
check_aws_credentials() {
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        log_error "AWS CLI is not configured or credentials are invalid."
        log_error "Please run 'aws configure' first."
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log_success "AWS credentials validated. Account ID: $ACCOUNT_ID"
    
    # Create or update .env.aws if it doesn't exist
    if [ ! -f .env.aws ]; then
        echo "export ACCOUNT_ID=$ACCOUNT_ID" > .env.aws
    fi
}

# Enhanced verification function
verify_setup() {
    log_step "Verifying AWS Twitter Automation Setup"
    
    local all_good=true
    
    # Check AWS credentials first
    check_aws_credentials
    
    # Source environment file if it exists
    if [ -f .env.aws ]; then
        source .env.aws
        log_info "Environment variables loaded from .env.aws"
    else
        log_warning ".env.aws file not found"
        all_good=false
    fi

    # echo
    log_info "🔍 Checking AWS Resources..."
    # echo

    # Check S3 bucket
    log_info "🪣 S3 Bucket:"
    # First try to check the specific bucket we need
    if aws s3api head-bucket --bucket twitter-automation-results 2>/dev/null; then
        log_success "S3 bucket found: twitter-automation-results"
    else
        # If that fails, fall back to listing (with proper error handling)
        S3_BUCKETS=$(aws s3 ls 2>/dev/null || echo "")
        if echo "$S3_BUCKETS" | grep -q twitter-automation; then
            BUCKET_NAME=$(echo "$S3_BUCKETS" | grep twitter-automation | awk '{print $3}' | head -1)
            log_success "S3 bucket found: $BUCKET_NAME"
        else
            log_error "S3 bucket 'twitter-automation-results' not found"
            log_info "Create with: aws s3 mb s3://twitter-automation-results"
            all_good=false
        fi
    fi

    # Check ECR repository and image
    log_info "🐳 ECR Repository and Image:"
    if aws ecr describe-repositories --repository-names twitter-automation --region us-east-1 >/dev/null 2>&1; then
        log_success "ECR repository 'twitter-automation' exists"
        
        if aws ecr describe-images --repository-name twitter-automation --region us-east-1 --query 'imageDetails[0].imageTags' >/dev/null 2>&1; then
            LATEST_TAGS=$(aws ecr describe-images --repository-name twitter-automation --region us-east-1 --query 'imageDetails[0].imageTags' --output text)
            log_success "Docker image found with tags: $LATEST_TAGS"
        else
            log_error "No Docker images found in ECR repository"
            log_info "Build and push with: docker build -t twitter-automation . && docker tag twitter-automation:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/twitter-automation:latest"
            all_good=false
        fi
    else
        log_error "ECR repository 'twitter-automation' not found"
        log_info "Create with: aws ecr create-repository --repository-name twitter-automation --region us-east-1"
        all_good=false
    fi

    # Check IAM roles
    log_info "👤 IAM Roles:"
    
    # ECS Task Execution Role
    if aws iam get-role --role-name ecsTaskExecutionRole-twitter >/dev/null 2>&1; then
        log_success "ECS Task Execution Role exists: ecsTaskExecutionRole-twitter"
    else
        log_error "ECS Task Execution Role not found: ecsTaskExecutionRole-twitter"
        all_good=false
    fi
    
    # ECS Task Role
    if aws iam get-role --role-name ecsTaskRole-twitter >/dev/null 2>&1; then
        log_success "ECS Task Role exists: ecsTaskRole-twitter"
    else
        log_error "ECS Task Role not found: ecsTaskRole-twitter"
        all_good=false
    fi
    
    # EventBridge Role
    if aws iam get-role --role-name EventBridgeECSRole-twitter >/dev/null 2>&1; then
        log_success "EventBridge ECS Role exists: EventBridgeECSRole-twitter"
    else
        log_error "EventBridge ECS Role not found: EventBridgeECSRole-twitter"
        all_good=false
    fi

    # Check VPC and networking
    log_info "🌐 VPC and Networking:"
    if [ -n "$DEFAULT_VPC" ] && [ -n "$SUBNET" ] && [ -n "$SECURITY_GROUP" ]; then
        # Verify VPC exists
        if aws ec2 describe-vpcs --vpc-ids $DEFAULT_VPC >/dev/null 2>&1; then
            log_success "VPC exists: $DEFAULT_VPC"
        else
            log_error "VPC not found: $DEFAULT_VPC"
            all_good=false
        fi
        
        # Verify subnet exists
        if aws ec2 describe-subnets --subnet-ids $SUBNET >/dev/null 2>&1; then
            log_success "Subnet exists: $SUBNET"
        else
            log_error "Subnet not found: $SUBNET"
            all_good=false
        fi
        
        # Verify security group exists
        if aws ec2 describe-security-groups --group-ids $SECURITY_GROUP >/dev/null 2>&1; then
            SG_NAME=$(aws ec2 describe-security-groups --group-ids $SECURITY_GROUP --query 'SecurityGroups[0].GroupName' --output text)
            log_success "Security Group exists: $SECURITY_GROUP ($SG_NAME)"
        else
            log_error "Security Group not found: $SECURITY_GROUP"
            all_good=false
        fi
    else
        log_error "Networking configuration missing from .env.aws"
        log_info "Expected: DEFAULT_VPC, SUBNET, SECURITY_GROUP"
        all_good=false
    fi

    # Check ECS cluster
    log_info "⚙️ ECS Cluster:"
    if aws ecs describe-clusters --clusters twitter-automation --query 'clusters[0].clusterName' --output text >/dev/null 2>&1; then
        CLUSTER_STATUS=$(aws ecs describe-clusters --clusters twitter-automation --query 'clusters[0].status' --output text)
        log_success "ECS Cluster exists: twitter-automation (Status: $CLUSTER_STATUS)"
    else
        log_error "ECS Cluster not found: twitter-automation"
        all_good=false
    fi

    # Check CloudWatch log group
    log_info "📋 CloudWatch Log Group:"
    if aws logs describe-log-groups --log-group-name-prefix /ecs/twitter-automation --query 'logGroups[0].logGroupName' --output text >/dev/null 2>&1; then
        RETENTION=$(aws logs describe-log-groups --log-group-name-prefix /ecs/twitter-automation --query 'logGroups[0].retentionInDays' --output text)
        log_success "CloudWatch Log Group exists: /ecs/twitter-automation (Retention: ${RETENTION:-unlimited} days)"
    else
        log_error "CloudWatch Log Group not found: /ecs/twitter-automation"
        all_good=false
    fi

    # Check ECS task definitions
    log_info "📋 ECS Task Definitions:"
    
    # Production task definition
    if aws ecs describe-task-definition --task-definition twitter-automation-production >/dev/null 2>&1; then
        PROD_REVISION=$(aws ecs describe-task-definition --task-definition twitter-automation-production --query 'taskDefinition.revision' --output text)
        log_success "Production Task Definition exists: twitter-automation-production:$PROD_REVISION"
    else
        log_error "Production Task Definition not found: twitter-automation-production"
        all_good=false
    fi
    
    # Test task definition
    if aws ecs describe-task-definition --task-definition twitter-automation-test >/dev/null 2>&1; then
        TEST_REVISION=$(aws ecs describe-task-definition --task-definition twitter-automation-test --query 'taskDefinition.revision' --output text)
        log_success "Test Task Definition exists: twitter-automation-test:$TEST_REVISION"
    else
        log_warning "Test Task Definition not found: twitter-automation-test (optional)"
    fi

    # Check EventBridge
    log_info "📅 EventBridge Schedule:"
    if aws events describe-rule --name twitter-automation-daily --region us-east-1 >/dev/null 2>&1; then
        SCHEDULE=$(aws events describe-rule --name twitter-automation-daily --region us-east-1 --query 'ScheduleExpression' --output text)
        STATE=$(aws events describe-rule --name twitter-automation-daily --region us-east-1 --query 'State' --output text)
        log_success "EventBridge Rule exists: twitter-automation-daily"
        log_info "  Schedule: $SCHEDULE"
        log_info "  State: $STATE"
        
        # Check targets
        TARGET_COUNT=$(aws events list-targets-by-rule --rule twitter-automation-daily --region us-east-1 --query 'length(Targets)' --output text)
        if [ "$TARGET_COUNT" -gt 0 ]; then
            log_success "EventBridge has $TARGET_COUNT target(s) configured"
        else
            log_error "EventBridge rule has no targets configured"
            all_good=false
        fi
    else
        log_error "EventBridge Rule not found: twitter-automation-daily"
        all_good=false
    fi

    echo
    # Overall status
    if [ "$all_good" = true ]; then
        log_success "🎉 All AWS resources are properly configured!"
        log_info "Your Twitter automation is ready to run daily at 9 AM UTC"
        echo
        log_info "Next steps:"
        log_info "• Run '$0 --test' to execute a test task"
        log_info "• Check CloudWatch logs at: /ecs/twitter-automation"
        log_info "• Monitor scheduled runs in AWS EventBridge console"
    else
        log_error "❌ Some AWS resources are missing or misconfigured"
        log_info "Run '$0 --setup' to create missing resources"
    fi
    echo
}

# Step 1: Create IAM Roles and Policies
create_iam_roles() {
    log_step "Creating IAM Roles and Policies"
    
    # Create ECS Execution Role trust policy
    cat > ecs-execution-role-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create ECS Execution Role
    log_info "Creating ECS Task Execution Role..."
    aws iam create-role \
        --role-name ecsTaskExecutionRole-twitter \
        --assume-role-policy-document file://ecs-execution-role-trust-policy.json \
        2>/dev/null || log_warning "Role may already exist"

    # Attach AWS managed policy for ECS task execution
    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole-twitter \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
        2>/dev/null || log_warning "Policy may already be attached"

    # Create ECS Task Role for S3 access
    log_info "Creating ECS Task Role..."
    aws iam create-role \
        --role-name ecsTaskRole-twitter \
        --assume-role-policy-document file://ecs-execution-role-trust-policy.json \
        2>/dev/null || log_warning "Role may already exist"

    # Create custom policy for S3 access
    cat > twitter-automation-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::twitter-automation-results",
                "arn:aws:s3:::twitter-automation-results/*"
            ]
        }
    ]
}
EOF

    # Create and attach S3 policy
    aws iam create-policy \
        --policy-name TwitterAutomationS3Policy \
        --policy-document file://twitter-automation-policy.json \
        2>/dev/null || log_warning "Policy may already exist"

    aws iam attach-role-policy \
        --role-name ecsTaskRole-twitter \
        --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/TwitterAutomationS3Policy \
        2>/dev/null || log_warning "Policy may already be attached"

    # Create Secrets Manager policy for brainlift-tracker access
    log_info "Creating Secrets Manager policy for brainlift-tracker access..."
    cat > twitter-automation-secrets-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "arn:aws:secretsmanager:us-east-1:$ACCOUNT_ID:secret:brainlift-tracker*"
            ]
        }
    ]
}
EOF

    # Create and attach Secrets Manager policy to execution role
    aws iam create-policy \
        --policy-name TwitterAutomationSecretsPolicy \
        --policy-document file://twitter-automation-secrets-policy.json \
        2>/dev/null || log_warning "Secrets policy may already exist"

    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole-twitter \
        --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/TwitterAutomationSecretsPolicy \
        2>/dev/null || log_warning "Secrets policy may already be attached"

    log_success "IAM Roles and Secrets Manager access created successfully"
}

# Step 2: Setup VPC, Subnets, and Security Groups
setup_networking() {
    log_step "Setting up VPC and Security Groups (mainly for Fargate)"
    
    # Get default VPC and subnets
    log_info "Finding default VPC..."
    DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
    log_info "Default VPC: $DEFAULT_VPC"

    # Get subnets in default VPC
    SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query "Subnets[*].SubnetId" --output text)
    log_info "Available subnets: $SUBNETS"

    # Use first subnet
    SUBNET=$(echo $SUBNETS | cut -d' ' -f1)
    log_info "Using subnet: $SUBNET"

    # Create security group for ECS tasks
    log_info "Creating security group..."
    SECURITY_GROUP=$(aws ec2 create-security-group \
        --group-name twitter-automation-sg \
        --description "Security group for Twitter automation ECS tasks" \
        --vpc-id $DEFAULT_VPC \
        --query "GroupId" --output text 2>/dev/null) || {
        # If group exists, get its ID
        SECURITY_GROUP=$(aws ec2 describe-security-groups \
            --filters "Name=group-name,Values=twitter-automation-sg" \
            --query "SecurityGroups[0].GroupId" --output text)
        log_warning "Security group already exists: $SECURITY_GROUP"
    }

    # Add outbound HTTPS rule (for Twitter API and S3)
    aws ec2 authorize-security-group-egress \
        --group-id $SECURITY_GROUP \
        --protocol tcp \
        --port 443 \
        --cidr 0.0.0.0/0 \
        2>/dev/null || log_warning "HTTPS egress rule may already exist"

    # Add outbound HTTP rule (for downloads)
    aws ec2 authorize-security-group-egress \
        --group-id $SECURITY_GROUP \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 \
        2>/dev/null || log_warning "HTTP egress rule may already exist"

    # Save environment variables for next steps
    echo "export DEFAULT_VPC=$DEFAULT_VPC" >> .env.aws
    echo "export SUBNET=$SUBNET" >> .env.aws
    echo "export SECURITY_GROUP=$SECURITY_GROUP" >> .env.aws

    log_success "VPC and Security Group configured"
}

# Step 3: Create CloudWatch Log Group
create_log_group() {
    log_step "Creating CloudWatch Log Group"
    
    # Create log group for ECS task logs
    aws logs create-log-group \
        --log-group-name /ecs/twitter-automation \
        --region us-east-1 \
        2>/dev/null || log_warning "Log group may already exist"

    # Set retention policy (keep logs for 7 days)
    aws logs put-retention-policy \
        --log-group-name /ecs/twitter-automation \
        --retention-in-days 7 \
        2>/dev/null || log_warning "Retention policy may already be set"

    log_success "CloudWatch Log Group created"
}

# Step 4: Create ECS Cluster
create_ecs_cluster() {
    log_step "Creating ECS Cluster"
    
    # Create ECS cluster
    aws ecs create-cluster \
        --cluster-name twitter-automation \
        --capacity-providers FARGATE \
        --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
        --region us-east-1 \
        2>/dev/null || log_warning "ECS cluster may already exist"

    log_success "ECS Cluster created"
}

# Step 5: Create ECS Task Definitions
create_task_definitions() {
    log_step "Creating ECS Task Definitions"
    
    # Create production task definition (without TEST_MODE)
    cat > ecs-task-definition-production.json << EOF
{
  "family": "twitter-automation-production",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/ecsTaskExecutionRole-twitter",
  "taskRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/ecsTaskRole-twitter",
  "containerDefinitions": [
    {
      "name": "twitter-automation",
      "image": "$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/twitter-automation:latest",
      "essential": true,
      "environment": [
        {
          "name": "S3_BUCKET_NAME",
          "value": "twitter-automation-results"
        },
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "us-east-1"
        },
        {
          "name": "PYTHONUNBUFFERED",
          "value": "1"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/twitter-automation",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs-production"
        }
      }
    }
  ]
}
EOF

    # Register production task definition
    aws ecs register-task-definition \
        --cli-input-json file://ecs-task-definition-production.json \
        --region us-east-1 > /dev/null

    log_success "Production task definition created"

    # Create test version of task definition
    cat > ecs-task-definition-test.json << EOF
{
  "family": "twitter-automation-test",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/ecsTaskExecutionRole-twitter",
  "taskRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/ecsTaskRole-twitter",
  "containerDefinitions": [
    {
      "name": "twitter-automation",
      "image": "$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/twitter-automation:latest",
      "essential": true,
      "environment": [
        {
          "name": "S3_BUCKET_NAME",
          "value": "twitter-automation-results"
        },
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "us-east-1"
        },
        {
          "name": "PYTHONUNBUFFERED",
          "value": "1"
        },
        {
          "name": "TEST_MODE",
          "value": "true"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/twitter-automation",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs-test"
        }
      }
    }
  ]
}
EOF

    log_success "Test task definition created"
}

# Step 6: Create EventBridge Rule and IAM Role
create_eventbridge_rule() {
    log_step "Creating EventBridge Rule"
    
    # Create EventBridge rule for daily execution at 9 AM UTC
    aws events put-rule \
        --name twitter-automation-daily \
        --schedule-expression "cron(0 9 * * ? *)" \
        --description "Daily Twitter automation at 9 AM UTC" \
        --region us-east-1 > /dev/null

    # Create IAM role for EventBridge to run ECS tasks
    cat > eventbridge-role-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "events.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name EventBridgeECSRole-twitter \
        --assume-role-policy-document file://eventbridge-role-trust-policy.json \
        2>/dev/null || log_warning "EventBridge role may already exist"

    # Create policy for EventBridge to run ECS tasks
    cat > eventbridge-ecs-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecs:RunTask"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
}
EOF

    aws iam create-policy \
        --policy-name EventBridgeECSPolicy \
        --policy-document file://eventbridge-ecs-policy.json \
        2>/dev/null || log_warning "EventBridge policy may already exist"

    # Attach policy to role
    aws iam attach-role-policy \
        --role-name EventBridgeECSRole-twitter \
        --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/EventBridgeECSPolicy \
        2>/dev/null || log_warning "Policy may already be attached"

    log_success "EventBridge rule and IAM role created"
}

# Step 7: Add EventBridge Target
add_eventbridge_target() {
    log_step "Adding EventBridge Target"
    
    # Load environment variables
    source .env.aws

    # Create EventBridge target configuration
    cat > eventbridge-target.json << EOF
[
  {
    "Id": "1",
    "Arn": "arn:aws:ecs:us-east-1:$ACCOUNT_ID:cluster/twitter-automation",
    "RoleArn": "arn:aws:iam::$ACCOUNT_ID:role/EventBridgeECSRole-twitter",
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:us-east-1:$ACCOUNT_ID:task-definition/twitter-automation-production",
      "LaunchType": "FARGATE",
      "NetworkConfiguration": {
        "awsvpcConfiguration": {
          "Subnets": ["$SUBNET"],
          "SecurityGroups": ["$SECURITY_GROUP"],
          "AssignPublicIp": "ENABLED"
        }
      }
    }
  }
]
EOF

    # Add target to EventBridge rule
    aws events put-targets \
        --rule twitter-automation-daily \
        --targets file://eventbridge-target.json \
        --region us-east-1 > /dev/null

    log_success "EventBridge target configured - will run daily at 9 AM UTC"
}

# Test task execution function
run_test_task() {
    log_step "Running Test Task"
    
    # Check credentials and load environment
    check_aws_credentials
    if [ ! -f .env.aws ]; then
        log_error ".env.aws file not found. Please run setup first."
        exit 1
    fi
    source .env.aws


    # Run test task
    log_info "🧪 Starting TEST ECS task..."

    TASK_ARN=$(aws ecs run-task \
        --cluster twitter-automation \
        --task-definition twitter-automation-test \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
        --region us-east-1 \
        --query "tasks[0].taskArn" --output text)

    log_info "🧪 Test task started: $TASK_ARN"

    # Monitor the task
    for i in {1..15}; do
        STATUS=$(aws ecs describe-tasks \
            --cluster twitter-automation \
            --tasks $TASK_ARN \
            --query "tasks[0].lastStatus" --output text)
        
        log_info "[$i/15] Test task status: $STATUS"
        
        if [ "$STATUS" = "STOPPED" ]; then
            log_success "Test task completed!"
            break
        fi
        
        sleep 15
    done

    log_success "Test run completed"
}

# Full setup function
run_full_setup() {
    log_info "🚀 Starting AWS Twitter Automation Complete Setup"
    log_info "This will create the entire AWS infrastructure for Twitter automation"
    echo
    
    # Confirm setup
    read -p "This will create AWS resources that may incur charges. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled by user"
        exit 0
    fi
    
    # Execute setup steps in order
    check_aws_credentials || handle_error "AWS Credentials Check"
    create_iam_roles || handle_error "IAM Roles Creation"
    setup_networking || handle_error "Networking Setup"
    create_log_group || handle_error "CloudWatch Log Group Creation"
    create_ecs_cluster || handle_error "ECS Cluster Creation"
    create_task_definitions || handle_error "ECS Task Definitions Creation"
    create_eventbridge_rule || handle_error "EventBridge Rule Creation"
    add_eventbridge_target || handle_error "EventBridge Target Addition"
    
    echo
    log_success "🎉 AWS Twitter Automation setup completed successfully!"
    log_info "The system is configured to run daily at 9 AM UTC"
    log_info "Environment variables saved in .env.aws file"
    log_info "Run '$0 --test' to execute a test task"
    echo
}

# Cleanup function for temporary files
cleanup_temp_files() {
    rm -f ecs-execution-role-trust-policy.json
    rm -f twitter-automation-policy.json
    rm -f ecs-task-definition-production.json
    rm -f ecs-task-definition-test.json
    rm -f eventbridge-role-trust-policy.json
    rm -f eventbridge-ecs-policy.json
    rm -f eventbridge-target.json
}

# Generate task definitions from templates
generate_task_definitions() {
    log_step "Generating ECS Task Definition Files"
    
    # For task generation, .env.aws MUST exist
    if [ ! -f .env.aws ]; then
        log_error ".env.aws file not found!"
        log_error "Task definition generation requires existing environment configuration."
        echo
        log_info "Please run one of the following first:"
        log_info "• ./aws_complete_setup.sh --setup    (creates full infrastructure + .env.aws)"
        log_info "• ./aws_complete_setup.sh --verify   (if infrastructure exists, creates .env.aws)"
        return 1
    fi
    
    # Load and validate required variables
    source .env.aws
    
    if [ -z "$ACCOUNT_ID" ]; then
        log_error "Invalid .env.aws file - missing ACCOUNT_ID"
        log_info "Delete .env.aws and run: ./aws_complete_setup.sh --setup"
        return 1
    fi
    
    # Auto-detect SECRET_ARN if needed
    if [ -z "$SECRET_ARN" ]; then
        SECRET_NAME="brainlift-tracker"
        if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 >/dev/null 2>&1; then
            SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 --query 'ARN' --output text)
            log_info "Auto-detected SECRET_ARN: $SECRET_ARN"
        else
            log_warning "No secrets manager secret found. Using placeholder."
            SECRET_ARN="arn:aws:secretsmanager:us-east-1:$ACCOUNT_ID:secret:twitter-automation-secrets"
        fi
    fi
    
    # Check if template files exist
    local test_template="ecs-task-definition-twitter-test.template.json"
    local prod_template="ecs-task-definition-twitter-production.template.json"
    
    if [ ! -f "$test_template" ]; then
        log_error "Template file not found: $test_template"
        log_info "Create template files first. See documentation for template structure."
        return 1
    fi
    
    if [ ! -f "$prod_template" ]; then
        log_error "Template file not found: $prod_template"
        return 1
    fi
    
    # Generate task definition files
    log_info "Generating task definitions with:"
    log_info "   Account ID: $ACCOUNT_ID"
    log_info "   Secret ARN: $SECRET_ARN"
    
    # Generate test task definition
    sed "s/{{ACCOUNT_ID}}/$ACCOUNT_ID/g; s|{{SECRET_ARN}}|$SECRET_ARN|g" \
        "$test_template" > "ecs-task-definition-twitter-test.json"
    
    # Generate production task definition
    sed "s/{{ACCOUNT_ID}}/$ACCOUNT_ID/g; s|{{SECRET_ARN}}|$SECRET_ARN|g" \
        "$prod_template" > "ecs-task-definition-twitter-production.json"
    
    # Verify generated files
    if [ -f "ecs-task-definition-twitter-test.json" ] && [ -f "ecs-task-definition-twitter-production.json" ]; then
        log_success "Task definition files generated successfully:"
        log_info "   - ecs-task-definition-twitter-test.json"
        log_info "   - ecs-task-definition-twitter-production.json"
        echo
        log_warning "⚠️  These files contain sensitive information (Account ID, ARNs)"
        log_warning "⚠️  Ensure they are in .gitignore and not committed to version control"
        echo
        log_info "Next steps:"
        log_info "• Register task definitions: ./register-task-definitions.sh"
        log_info "• Or register manually: aws ecs register-task-definition --cli-input-json file://ecs-task-definition-twitter-test.json"
    else
        log_error "Failed to generate task definition files"
        return 1
    fi
}

# Main execution function
main() {
    # Trap to handle cleanup on exit
    trap cleanup_temp_files EXIT
    
    # Parse command line arguments
    case "${1:-}" in
        --setup|-s)
            run_full_setup
            ;;
        --test|-t)
            run_test_task
            ;;
        --verify|-v|"")
            verify_setup
            ;;
        --generate-tasks|-g)
            check_aws_credentials
            generate_task_definitions
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
