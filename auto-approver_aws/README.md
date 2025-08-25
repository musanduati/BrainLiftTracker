# AWS Twitter Automation System

## Overview

This is an **AWS-based Twitter automation system** that processes Twitter follow requests automatically using Selenium browser automation. The system runs on **AWS ECS Fargate** and processes accounts sequentially to respect external constraints.

### Key Features

- **🤖 Automated Follow Request Approval**: Processes pending Twitter follow requests automatically
- **☁️ AWS Cloud-Native**: Runs on ECS Fargate with no server management required  
- **📅 Daily Scheduling**: Automatically executes thrice a day via EventBridge
- **🔄 Sequential Processing**: Processes accounts one by one (no parallelism to prevent Twitter lockouts)
- **💾 Result Storage**: Saves detailed results and metrics to S3
- **📊 Monitoring**: CloudWatch logging and monitoring
- **🧪 Test Mode**: Separate test environment with single account processing
- **🏷️ Environment Isolation**: Test and production images are completely isolated
- **🔐 Secure Secrets Management**: Uses AWS Secrets Manager with template-based configuration
- **💰 Cost-Effective**: Costs are incurred only when it runs

---

## Architecture

```
EventBridge (daily trigger) → ECS Fargate Task → Sequential Account Processing → Results to S3
                                     ↓
                            Chrome/ChromeDriver → Twitter Login → Auto-approve Requests
```

### AWS Resources Used

- **ECS Fargate**: Serverless container execution
- **ECR**: Docker image repository  
- **EventBridge**: Daily scheduling
- **CloudWatch**: Logging and monitoring
- **S3**: Results storage
- **Secrets Manager**: Secure credential storage
- **IAM**: Security roles and policies
- **VPC**: Networking (default VPC)

---

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed and running
- Account files ready in `../auto-approver/` directory

### 1. Complete Setup (First Time)

```bash
cd auto-approver_aws/

# Run complete AWS infrastructure setup
./aws_complete_setup.sh --setup
```

This creates all AWS resources needed for the automation.

### 2. Generate Task Definitions

```bash
# Generate task definition files from templates
./aws_complete_setup.sh --generate-tasks
```

### 3. Build and Deploy

```bash
# Build and push test Docker image (default, safe)
./build_push_twitter_automation_img.sh test

# Or build production image (when ready)
./build_push_twitter_automation_img.sh prod
```

### 4. Register Task Definitions

```bash
# Register both test and production task definitions
./register-task-definitions.sh
```

### 5. Test the System

```bash
# Run a test with single account
./aws_complete_setup.sh --test
```

### 6. Verify Setup

```bash
# Check all AWS resources
./aws_complete_setup.sh --verify
```

---

## Improved Practices

### Environment-Specific Image Management

The system uses **environment-specific tagging** for better isolation:

- **Test Environment**: `test-latest`, `test-YYYYMMDD-HHMMSS`
- **Production Environment**: `prod-latest`, `prod-YYYYMMDD-HHMMSS`

```bash
# Examples
./build_push_twitter_automation_img.sh test     # Safe default
./build_push_twitter_automation_img.sh prod     # Production deployment
```

### Template-Based Task Definitions

Task definitions use **templates with placeholders** to avoid hardcoding sensitive information:

- `ecs-task-definition-twitter-test.template.json` → `ecs-task-definition-twitter-test.json`
- `ecs-task-definition-twitter-production.template.json` → `ecs-task-definition-twitter-production.json`

**Security**: Generated files are in `.gitignore` and never committed to version control.

### Centralized Secrets Management

All credentials are managed through **AWS Secrets Manager**:

- **Secret Name**: `brainlift-tracker` (shared with workflowy system)
- **Environment Variable**: `BRAINLIFT_TRACKER`
- **Auto-loaded**: Credentials automatically available as environment variables

---

## File Structure

```
auto-approver_aws/
├── aws_complete_setup.sh                          # 🎯 Main setup and management script
├── build_push_twitter_automation_img.sh           # 🐳 Environment-aware Docker build script
├── register-task-definitions.sh                   # 📋 Task definition registration
├── aws_wrapper.py                                 # 🐍 AWS integration wrapper with secrets loading
├── dockerfile                                     # 🐳 Container definition
├── requirements_aws.txt                           # 📦 Python dependencies
├── .env.aws                                       # 🔧 Environment variables (auto-generated)
├── ecs-task-definition-twitter-test.template.json      # 📋 Test task template
├── ecs-task-definition-twitter-production.template.json # 📋 Production task template
├── ecs-task-definition-twitter-test.json               # 📋 Generated test task (git-ignored)
└── ecs-task-definition-twitter-production.json         # 📋 Generated production task (git-ignored)
```

---

## Account Configuration

### CSV File Format

The system reads accounts from CSV files in `../auto-approver/`:

- **Production**: `accounts_academics.csv`, `accounts_superbuilders.csv`, `accounts_finops.csv`, `accounts_klair.csv`
- **Testing**: `accounts_test.csv`

**CSV Format:**
```csv
username,password,email,max_approvals,delay_seconds
@username,password123,email@example.com,50,3
```

### Test vs Production Mode

- **Test Mode**: `TEST_MODE=true` → Uses `accounts_test.csv` (1-2 accounts)
- **Production Mode**: `TEST_MODE=false` → Uses all production CSV files

---

## Usage Guide

### Daily Operation

The system **runs automatically** thrice a day 00:00 AM, 08:00 AM, and 04:00 PM UTC. No manual intervention required.

### Manual Operations

#### Build and Deploy New Version
```bash
# Test version (safe default)
./build_push_twitter_automation_img.sh test
./register-task-definitions.sh
./aws_complete_setup.sh --test

# Production version (after testing)
./build_push_twitter_automation_img.sh prod
./register-task-definitions.sh
```

#### Run Test Task
```bash
./aws_complete_setup.sh --test
```

#### Check System Status
```bash
./aws_complete_setup.sh --verify
```

#### View Recent Logs
```bash
# Get latest log stream
LOG_STREAM=$(aws logs describe-log-streams \
    --log-group-name /ecs/twitter-automation \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --query "logStreams[0].logStreamName" --output text)

# View logs
aws logs get-log-events \
    --log-group-name /ecs/twitter-automation \
    --log-stream-name $LOG_STREAM \
    --query "events[*].message" --output text
```

#### Update Account List
```bash
# 1. Update CSV files in ../auto-approver/
# 2. Rebuild Docker image
./build_push_twitter_automation_img.sh test
# 3. Test changes
./aws_complete_setup.sh --test
```

#### Regenerate Task Definitions
```bash
# After infrastructure changes
./aws_complete_setup.sh --generate-tasks
./register-task-definitions.sh
```

---

## Results

### S3 Results
Results are saved to: `s3://twitter-automation-results/results/YYYY/MM/DD/`

**Result Format:**
```json
{
  "batch_id": "fargate-20241208-090000",
  "timestamp": "2024-12-08T09:00:00Z",
  "execution_environment": "AWS_ECS_FARGATE_PRODUCTION",
  "summary": {
    "total_accounts": 169,
    "successful_accounts": 165,
    "total_approvals": 1247,
    "success_rate": 97.6,
    "by_source_file": {
      "accounts_academics.csv": {"accounts": 131, "successful": 128, "approvals": 982},
      "accounts_superbuilders.csv": {"accounts": 38, "successful": 37, "approvals": 265}
    }
  }
}
```

### Log Locations
- **CloudWatch**: `/ecs/twitter-automation`
- **Retention**: 7 days
- **Streams**: `ecs-production/*` and `ecs-test/*`

---

## Secrets Management

### Required Secrets in `brainlift-tracker`

The system expects these keys in the AWS Secrets Manager secret:

```json
{
  "GMAIL_USERNAME": "brainlift.monitor@trilogy.com",
  "GMAIL_APP_PASSWORD": "your-gmail-app-password",
  "API_BASE": "http://IP_ADDRESS/api/v1",
  "API_KEY": "your-api-key"
}
```

---

## Cost Analysis

### Monthly Costs (Estimated)

| Component | Specification | Monthly Cost |
|-----------|---------------|--------------|
| **ECS Fargate** | 2 vCPU, 4GB × 2hrs/day × 30 days | **$12.10** |
| **S3 Storage** | ~1GB results/logs | **$0.23** |
| **CloudWatch** | Log storage + dashboard | **$2.00** |
| **Secrets Manager** | 1 secret | **$0.40** |
| **Data Transfer** | Minimal | **$1.00** |
| **ECR** | Docker image storage | **$0.50** |
| **Total** |  | **~$16.23/month** |

### Cost Optimization
- **No idle costs**: Only pay when tasks are running
- **Environment isolation**: Test and prod images stored separately
- **Automatic scaling**: Resources allocated only during execution
- **Log retention**: 7 days to control storage costs

---

## Security

### IAM Roles
- **ECS Task Execution Role**: Container management + Secrets Manager access
- **ECS Task Role**: S3 access for results
- **EventBridge Role**: Task scheduling

### Secrets Management
- **Centralized**: All credentials in AWS Secrets Manager
- **Auto-loaded**: Secrets automatically injected as environment variables
- **Shared**: Uses same `brainlift-tracker` secret as workflowy system

### Network Security
- **VPC**: Runs in default VPC
- **Security Groups**: Outbound HTTPS/HTTP only
- **No inbound access**: Containers are not accessible from internet

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails
```bash
# Clear Docker cache and rebuild
docker system prune -f
./build_push_twitter_automation_img.sh test
```

#### 2. Task Definition Generation Fails
```bash
# Check template files exist
ls -la ecs-task-definition-twitter-*.template.json

# Regenerate with proper setup
./aws_complete_setup.sh --generate-tasks
```

#### 3. Secrets Not Loading
```bash
# Check secret exists and has required keys
aws secretsmanager get-secret-value \
    --secret-id brainlift-tracker \
    --region us-east-1

# Verify IAM permissions
aws iam list-attached-role-policies \
    --role-name ecsTaskExecutionRole-twitter
```

#### 4. Task Fails to Start
```bash
# Check task definition
aws ecs describe-task-definition --task-definition twitter-automation-test

# Check recent task failures
aws ecs describe-tasks --cluster twitter-automation --include TAGS
```

#### 5. Gmail Credentials Not Working
- Verify Gmail App Password is correct (not regular password)
- Check that GMAIL_USERNAME and GMAIL_APP_PASSWORD are in brainlift-tracker secret
- Ensure secrets are being loaded in container logs

### Debug Commands

#### Check Image Tags
```bash
# List all images in ECR
aws ecr describe-images \
    --repository-name twitter-automation \
    --region us-east-1 \
    --query 'imageDetails[*].imageTags' \
    --output table
```

#### Manual Task Execution
```bash
# Run test task manually
aws ecs run-task \
    --cluster twitter-automation \
    --task-definition twitter-automation-test \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Development

### Adding New Features
1. Modify `aws_wrapper.py` or automation scripts
2. Update `dockerfile` if needed
3. Build test image: `./build_push_twitter_automation_img.sh test`
4. Test: `./aws_complete_setup.sh --test`
5. Build prod image: `./build_push_twitter_automation_img.sh prod`

### Environment Variables
```bash
# Key environment variables (set in task definition templates)
TEST_MODE=true|false          # Toggle test vs production
S3_BUCKET_NAME=bucket-name    # Results storage
AWS_DEFAULT_REGION=us-east-1  # AWS region
ENVIRONMENT=test|prod         # Current environment
```

---

## Support

### AWS Console Links
- **ECS Cluster**: https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/twitter-automation
- **CloudWatch Logs**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Ftwitter-automation
- **EventBridge Rules**: https://console.aws.amazon.com/events/home?region=us-east-1#/eventbus/default/rules/twitter-automation-daily
- **S3 Bucket**: https://console.aws.amazon.com/s3/buckets/twitter-automation-results
- **Secrets Manager**: https://console.aws.amazon.com/secretsmanager/home?region=us-east-1#!/secret?name=brainlift-tracker

### Emergency Procedures

#### Stop Automation
```bash
# Disable EventBridge rule
aws events disable-rule --name twitter-automation-daily --region us-east-1
```

#### Restart Automation
```bash
# Re-enable EventBridge rule  
aws events enable-rule --name twitter-automation-daily --region us-east-1
```

#### Rollback to Previous Image
```bash
# List available tags
aws ecr describe-images --repository-name twitter-automation --region us-east-1

# Update task definition to use specific tag
# Edit generated task definition and re-register
```

---

**🎯 System Status**: Ready for daily production use with improved practices

**📅 Next Run**:  Thrice a day

**📊 Accounts**: 169+ total across multiple CSV files

**⏱️ Duration**: ~2 hours per run

**💰 Cost**: ~$16/month

**🔒 Security**: AWS Secrets Manager + IAM roles

This comprehensive README.md provides everything needed to understand, deploy, operate, and maintain the improved AWS Twitter automation system.
