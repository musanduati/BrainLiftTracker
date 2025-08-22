#!/bin/bash

# ============================================================================
# Workflowy ECS Complete Setup Script
# Combines IAM roles, secrets, ECS resources, and verification
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ACCOUNT_ID=""
SECRET_NAME="brainlift-tracker"
SECRET_ARN=""
CLUSTER_NAME="workflowy-processor-cluster"
LOG_GROUP="/ecs/workflowy-processor"

# Logging functions
log_info() { printf "${BLUE}ℹ️  %s${NC}\n" "$1"; }
log_success() { printf "${GREEN}✅ %s${NC}\n" "$1"; }
log_warning() { printf "${YELLOW}⚠️  %s${NC}\n" "$1"; }
log_error() { printf "${RED}❌ %s${NC}\n" "$1"; }
log_step() { printf "\n${BLUE}==== %s ====${NC}\n" "$1"; }

# Help function
show_help() {
    echo "Workflowy ECS Complete Setup Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --setup, -s           Run complete setup (create missing resources)"
    echo "  --verify, -v          Verify existing setup only (default)"
    echo "  --generate-tasks, -t  Generate task definition files from templates"
    echo "  --force-recreate      Force recreate all resources"
    echo "  --help, -h            Show this help message"
    echo
    echo "Examples:"
    echo "  $0                    # Verify existing setup"
    echo "  $0 --setup           # Create missing resources"  
    echo "  $0 --generate-tasks  # Generate task definition files"
    echo "  $0 --verify          # Just verify (same as default)"
}

# Initialize variables - only for setup/verify operations
init_variables() {
    log_step "Initializing Configuration"
    
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        log_error "AWS CLI is not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log_success "AWS credentials validated. Account ID: $ACCOUNT_ID"
    
    # For setup operations, we may not have .env.aws yet - that's expected
    # For verify operations, we expect it to exist
    if [ -f .env.aws ]; then
        source .env.aws
        log_info "Environment variables loaded from .env.aws"
    else
        log_info ".env.aws will be created during setup process"
    fi
    
    # Set basic derived values
    SECRET_ARN="arn:aws:secretsmanager:us-east-1:$ACCOUNT_ID:secret:$SECRET_NAME"
    ECR_URI_WORKFLOWY_PROCESSOR="$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/workflowy-processor"
}

# Check if resource exists
check_iam_role() {
    local role_name="$1"
    aws iam get-role --role-name "$role_name" >/dev/null 2>&1
}

check_iam_policy() {
    local policy_arn="$1"
    aws iam get-policy --policy-arn "$policy_arn" >/dev/null 2>&1
}

check_secret() {
    aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 >/dev/null 2>&1
}

check_ecs_cluster() {
    local cluster_status=$(aws ecs describe-clusters --clusters "$CLUSTER_NAME" --query 'clusters[0].status' --output text 2>/dev/null)
    [ "$cluster_status" = "ACTIVE" ]
}

check_log_group() {
    aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --query 'logGroups[0].logGroupName' --output text >/dev/null 2>&1
}

check_ecr_repository() {
    aws ecr describe-repositories --repository-names workflowy-processor --region us-east-1 >/dev/null 2>&1
}

# Verification functions
verify_setup() {
    log_step "Verifying Workflowy ECS Setup"
    
    local all_good=true
    local create_env_file=false
    
    # If .env.aws doesn't exist but we're verifying, we may need to create it
    if [ ! -f .env.aws ]; then
        log_warning ".env.aws not found - will create if infrastructure exists"
        create_env_file=true
    fi
    
    # Check IAM Roles
    log_info "👤 IAM Roles:"
    if check_iam_role "ecsTaskExecutionRole-workflowy"; then
        log_success "ECS Task Execution Role exists"
    else
        log_error "ECS Task Execution Role missing: ecsTaskExecutionRole-workflowy"
        all_good=false
    fi
    
    if check_iam_role "ecsTaskRole-workflowy"; then
        log_success "ECS Task Role exists"
    else
        log_error "ECS Task Role missing: ecsTaskRole-workflowy"
        all_good=false
    fi
    
    # Check Secrets Manager
    log_info "🔐 Secrets Manager:"
    if check_secret; then
        SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 --query 'ARN' --output text)
        log_success "Secret exists: $SECRET_NAME"
        log_info "   ARN: $SECRET_ARN"
        
        # Check if execution role has access to secret
        local policy_arn="arn:aws:iam::$ACCOUNT_ID:policy/WorkflowySecretsPolicy"
        if check_iam_policy "$policy_arn"; then
            log_success "Secrets Manager policy exists"
            
            # Check if policy is attached to execution role
            if aws iam list-attached-role-policies --role-name ecsTaskExecutionRole-workflowy --query "AttachedPolicies[?PolicyArn=='$policy_arn']" --output text | grep -q "WorkflowySecretsPolicy"; then
                log_success "Secrets policy attached to execution role"
            else
                log_error "Secrets policy not attached to execution role"
                all_good=false
            fi
        else
            log_error "Secrets Manager policy missing"
            all_good=false
        fi
    else
        log_error "Secret missing: $SECRET_NAME"
        all_good=false
    fi
    
    # Check ECS Resources
    log_info "⚙️ ECS Resources:"
    if check_ecs_cluster; then
        log_success "ECS Cluster exists: $CLUSTER_NAME"
    else
        log_error "ECS Cluster missing: $CLUSTER_NAME"
        all_good=false
    fi
    
    if check_log_group; then
        log_success "CloudWatch Log Group exists: $LOG_GROUP"
    else
        log_error "CloudWatch Log Group missing: $LOG_GROUP"
        all_good=false
    fi
    
    if check_ecr_repository; then
        log_success "ECR Repository exists: workflowy-processor"
    else
        log_error "ECR Repository missing: workflowy-processor"
        all_good=false
    fi
    
    # Check networking (from existing twitter automation)
    log_info "🌐 Networking:"
    if [ -n "$DEFAULT_VPC" ] && [ -n "$SUBNET" ] && [ -n "$SECURITY_GROUP" ]; then
        if aws ec2 describe-vpcs --vpc-ids "$DEFAULT_VPC" >/dev/null 2>&1; then
            log_success "VPC exists: $DEFAULT_VPC"
        else
            log_error "VPC not found: $DEFAULT_VPC"
            all_good=false
        fi
        
        if aws ec2 describe-subnets --subnet-ids "$SUBNET" >/dev/null 2>&1; then
            log_success "Subnet exists: $SUBNET"
        else
            log_error "Subnet not found: $SUBNET"
            all_good=false
        fi
        
        if aws ec2 describe-security-groups --group-ids "$SECURITY_GROUP" >/dev/null 2>&1; then
            log_success "Security Group exists: $SECURITY_GROUP"
        else
            log_error "Security Group not found: $SECURITY_GROUP"
            all_good=false
        fi
    else
        log_error "Networking configuration missing from .env.aws"
        all_good=false
    fi
    
    # At the end of verification, if infrastructure exists but .env.aws is missing
    if [ "$all_good" = true ] && [ "$create_env_file" = true ]; then
        log_info "🔧 Infrastructure exists but .env.aws missing - creating it..."
        setup_networking  # This will detect existing networking
        save_environment_config
        log_success "✅ .env.aws created from existing infrastructure"
    fi
    
    # Summary
    echo
    if [ "$all_good" = true ]; then
        log_success "🎉 All resources are properly configured!"
        log_info "Ready to generate task definitions: ./setup-workflowy-complete.sh --generate-tasks"
        log_info "Or run full workflow: ./build_push_workflowy_img.sh"
    else
        log_error "❌ Some resources are missing or misconfigured"
        log_info "Run '$0 --setup' to create missing resources"
    fi
    echo
}

# Setup functions
create_iam_roles() {
    log_step "Creating IAM Roles"
    
    # Trust policy for ECS tasks
    cat > ecs-trust-policy.json << 'EOF'
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
    
    # Create ECS Task Execution Role
    if ! check_iam_role "ecsTaskExecutionRole-workflowy"; then
        log_info "Creating ECS Task Execution Role..."
        aws iam create-role \
            --role-name ecsTaskExecutionRole-workflowy \
            --assume-role-policy-document file://ecs-trust-policy.json
        
        aws iam attach-role-policy \
            --role-name ecsTaskExecutionRole-workflowy \
            --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
        
        log_success "ECS Task Execution Role created"
    else
        log_info "ECS Task Execution Role already exists"
    fi
    
    # Create ECS Task Role
    if ! check_iam_role "ecsTaskRole-workflowy"; then
        log_info "Creating ECS Task Role..."
        aws iam create-role \
            --role-name ecsTaskRole-workflowy \
            --assume-role-policy-document file://ecs-trust-policy.json
        
        # Attach basic AWS service policies
        aws iam attach-role-policy \
            --role-name ecsTaskRole-workflowy \
            --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
        
        aws iam attach-role-policy \
            --role-name ecsTaskRole-workflowy \
            --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
        
        log_success "ECS Task Role created"
    else
        log_info "ECS Task Role already exists"
    fi
    
    rm -f ecs-trust-policy.json
}

create_secrets_manager_setup() {
    log_step "Setting up Secrets Manager"
    
    # Create secret if it doesn't exist
    if ! check_secret; then
        log_info "Creating secret: $SECRET_NAME"
        aws secretsmanager create-secret \
            --name "$SECRET_NAME" \
            --description "API keys and configuration for Workflowy processor" \
            --secret-string '{
                "API_BASE": "REPLACE-WITH-ACTUAL-API-BASE",
                "API_KEY": "REPLACE-WITH-ACTUAL-API-KEY",
                "OPENAI_API_KEY": "REPLACE-WITH-ACTUAL-OPENAI-KEY"
            }' \
            --region us-east-1
        
        SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 --query 'ARN' --output text)
        log_success "Secret created: $SECRET_NAME"
        log_warning "⚠️ Remember to update with real values using AWS Console or CLI"
    else
        SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 --query 'ARN' --output text)
        log_info "Secret already exists: $SECRET_NAME"
    fi
    
    # Create and attach secrets policy
    local policy_arn="arn:aws:iam::$ACCOUNT_ID:policy/WorkflowySecretsPolicy"
    if ! check_iam_policy "$policy_arn"; then
        log_info "Creating Secrets Manager policy..."
        cat > workflowy-secrets-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "$SECRET_ARN*"
            ]
        }
    ]
}
EOF
        
        aws iam create-policy \
            --policy-name WorkflowySecretsPolicy \
            --policy-document file://workflowy-secrets-policy.json
        
        log_success "Secrets Manager policy created"
        rm -f workflowy-secrets-policy.json
    else
        log_info "Secrets Manager policy already exists"
    fi
    
    # Attach policy to execution role
    if ! aws iam list-attached-role-policies --role-name ecsTaskExecutionRole-workflowy --query "AttachedPolicies[?PolicyArn=='$policy_arn']" --output text | grep -q "WorkflowySecretsPolicy"; then
        log_info "Attaching secrets policy to execution role..."
        aws iam attach-role-policy \
            --role-name ecsTaskExecutionRole-workflowy \
            --policy-arn "$policy_arn"
        
        log_success "Secrets policy attached to execution role"
    else
        log_info "Secrets policy already attached to execution role"
    fi
}

create_ecs_resources() {
    log_step "Setting up ECS Resources"
    
    # Create ECS cluster
    if ! check_ecs_cluster; then
        log_info "Creating ECS cluster: $CLUSTER_NAME"
        aws ecs create-cluster \
            --cluster-name "$CLUSTER_NAME" \
            --capacity-providers FARGATE FARGATE_SPOT \
            --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=80 capacityProvider=FARGATE,weight=20 \
            --region us-east-1
        
        log_success "ECS Cluster created: $CLUSTER_NAME"
    else
        log_info "ECS Cluster already exists: $CLUSTER_NAME"
    fi
    
    # Create CloudWatch log group
    if ! check_log_group; then
        log_info "Creating CloudWatch log group: $LOG_GROUP"
        aws logs create-log-group \
            --log-group-name "$LOG_GROUP" \
            --region us-east-1
        
        aws logs put-retention-policy \
            --log-group-name "$LOG_GROUP" \
            --retention-in-days 14
        
        log_success "CloudWatch Log Group created: $LOG_GROUP"
    else
        log_info "CloudWatch Log Group already exists: $LOG_GROUP"
    fi
    
    # Create ECR repository
    if ! check_ecr_repository; then
        log_info "Creating ECR repository: workflowy-processor"
        aws ecr create-repository \
            --repository-name workflowy-processor \
            --region us-east-1
        
        log_success "ECR Repository created: workflowy-processor"
    else
        log_info "ECR Repository already exists: workflowy-processor"
    fi
}

setup_networking() {
    log_step "Setting up Networking"
    
    # Check if networking is already configured
    if [ -n "$DEFAULT_VPC" ] && [ -n "$SUBNET" ] && [ -n "$SECURITY_GROUP" ]; then
        log_info "Networking already configured in .env.aws"
        return
    fi
    
    # Get default VPC
    log_info "Finding default VPC..."
    DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
    log_info "Default VPC: $DEFAULT_VPC"
    
    # Get first subnet
    SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query "Subnets[*].SubnetId" --output text)
    SUBNET=$(echo $SUBNETS | cut -d' ' -f1)
    log_info "Using subnet: $SUBNET"
    
    # Create or find security group
    SECURITY_GROUP=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=workflowy-processor-sg" \
        --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)
    
    if [ "$SECURITY_GROUP" = "None" ] || [ -z "$SECURITY_GROUP" ]; then
        log_info "Creating security group..."
        SECURITY_GROUP=$(aws ec2 create-security-group \
            --group-name workflowy-processor-sg \
            --description "Security group for Workflowy ECS tasks" \
            --vpc-id "$DEFAULT_VPC" \
            --query "GroupId" --output text)
        
        # Add egress rules for HTTPS and HTTP
        aws ec2 authorize-security-group-egress \
            --group-id "$SECURITY_GROUP" \
            --protocol tcp --port 443 --cidr 0.0.0.0/0 2>/dev/null || true
        
        aws ec2 authorize-security-group-egress \
            --group-id "$SECURITY_GROUP" \
            --protocol tcp --port 80 --cidr 0.0.0.0/0 2>/dev/null || true
        
        log_success "Security group created: $SECURITY_GROUP"
    else
        log_info "Security group already exists: $SECURITY_GROUP"
    fi
    
    # Save to environment file
    {
        echo "export ACCOUNT_ID=$ACCOUNT_ID"
        echo "export DEFAULT_VPC=$DEFAULT_VPC"
        echo "export SUBNET=$SUBNET"
        echo "export SECURITY_GROUP=$SECURITY_GROUP"
        echo "export SECRET_ARN=$SECRET_ARN"
        echo "export ECR_URI_WORKFLOWY_PROCESSOR=$ECR_URI_WORKFLOWY_PROCESSOR"
    } > .env.aws
    
    log_success "Networking configured and saved to .env.aws"
}

run_complete_setup() {
    log_info "🚀 Running complete Workflowy ECS setup..."
    echo
    
    init_variables
    create_iam_roles
    create_secrets_manager_setup
    create_ecs_resources
    setup_networking
    
    # Generate task definitions as part of complete setup
    generate_task_definitions
    
    echo
    log_success "🎉 Complete setup finished!"
    log_info "Next steps:"
    log_info "1. Update secret values: aws secretsmanager update-secret --secret-id $SECRET_NAME --secret-string '{...}'"
    log_info "2. Build Docker image: ./build_push_workflowy_img.sh"
    log_info "3. Register task definitions: ./register-task-definitions.sh"
    log_info "4. Test deployment: ./run-workflowy-test.sh"
}

# Add the generate task definitions function
generate_task_definitions() {
    log_step "Generating ECS Task Definition Files"
    
    # For task generation, .env.aws MUST exist
    if [ ! -f .env.aws ]; then
        log_error ".env.aws file not found!"
        log_error "Task definition generation requires existing environment configuration."
        echo
        log_info "Please run one of the following first:"
        log_info "• ./setup-workflowy-complete.sh --setup    (creates full infrastructure + .env.aws)"
        log_info "• ./setup-workflowy-complete.sh --verify   (if infrastructure exists, creates .env.aws)"
        return 1
    fi
    
    # Load and validate required variables
    source .env.aws
    
    if [ -z "$ACCOUNT_ID" ] || [ -z "$SECRET_ARN" ]; then
        log_error "Invalid .env.aws file - missing required variables"
        log_error "Expected: ACCOUNT_ID, SECRET_ARN"
        log_info "Delete .env.aws and run: ./setup-workflowy-complete.sh --setup"
        return 1
    fi
    
    # Check if template files exist
    local test_template="ecs-task-definition-workflowy-test.template.json"
    local prod_template="ecs-task-definition-workflowy-production.template.json"
    
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
        "$test_template" > "ecs-task-definition-workflowy-test.json"
    
    # Generate production task definition
    sed "s/{{ACCOUNT_ID}}/$ACCOUNT_ID/g; s|{{SECRET_ARN}}|$SECRET_ARN|g" \
        "$prod_template" > "ecs-task-definition-workflowy-production.json"
    
    # Verify generated files
    if [ -f "ecs-task-definition-workflowy-test.json" ] && [ -f "ecs-task-definition-workflowy-production.json" ]; then
        log_success "Task definition files generated successfully:"
        log_info "   - ecs-task-definition-workflowy-test.json"
        log_info "   - ecs-task-definition-workflowy-production.json"
        echo
        log_warning "⚠️  These files contain sensitive information (Account ID, ARNs)"
        log_warning "⚠️  Ensure they are in .gitignore and not committed to version control"
        echo
        log_info "Next steps:"
        log_info "• Register task definitions: ./register-task-definitions.sh"
        log_info "• Or register manually: aws ecs register-task-definition --cli-input-json file://ecs-task-definition-workflowy-test.json"
    else
        log_error "Failed to generate task definition files"
        return 1
    fi
}

# Add a function to save environment configuration
save_environment_config() {
    log_info "💾 Saving configuration to .env.aws..."
    
    # Auto-detect SECRET_ARN if needed
    if [ -z "$SECRET_ARN" ] && check_secret; then
        SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region us-east-1 --query 'ARN' --output text 2>/dev/null || echo "")
    fi
    
    cat > .env.aws << EOF
# Workflowy ECS Configuration
# Generated by setup-workflowy-complete.sh on $(date)

export ACCOUNT_ID=$ACCOUNT_ID
export DEFAULT_VPC=$DEFAULT_VPC
export SUBNET=$SUBNET  
export SECURITY_GROUP=$SECURITY_GROUP
export SECRET_ARN=$SECRET_ARN
export SECRET_NAME=$SECRET_NAME
export ECR_URI_WORKFLOWY_PROCESSOR=$ECR_URI_WORKFLOWY_PROCESSOR
export CLUSTER_NAME=$CLUSTER_NAME
export LOG_GROUP=$LOG_GROUP
EOF
    
    log_success "Configuration saved to .env.aws"
    log_info "This file is required for other scripts (build, deploy, etc.)"
}

# Main execution
main() {
    case "${1:-}" in
        --setup|-s)
            run_complete_setup
            ;;
        --verify|-v|"")
            init_variables
            verify_setup
            ;;
        --generate-tasks|-t)
            init_variables
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

# Cleanup on exit
cleanup() {
    rm -f ecs-trust-policy.json workflowy-secrets-policy.json
}
trap cleanup EXIT

main "$@"
