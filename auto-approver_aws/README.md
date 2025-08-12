# AWS Twitter Automation System

## Overview

This is an **AWS-based Twitter automation system** that processes Twitter follow requests automatically using Selenium browser automation. The system runs on **AWS ECS Fargate** and processes accounts sequentially to respect external constraints.

### Key Features

- **🤖 Automated Follow Request Approval**: Processes pending Twitter follow requests automatically
- **☁️ AWS Cloud-Native**: Runs on ECS Fargate with no server management required
- **📅 Daily Scheduling**: Automatically executes daily at 9 AM UTC via EventBridge
- **🔄 Sequential Processing**: Processes accounts one by one (no parallelism to prevent from getting locked out from Twitter side of things)
- **💾 Result Storage**: Saves detailed results and metrics to S3
- **📊 Monitoring**: CloudWatch logging and monitoring
- **🧪 Test Mode**: Separate test environment with single account processing
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

### 2. Build and Deploy

```bash
# Build and push Docker image
./build_push_docker_img.sh
```

### 3. Test the System

```bash
# Run a test with single account
./aws_complete_setup.sh --test
```

### 4. Verify Setup

```bash
# Check all AWS resources
./aws_complete_setup.sh --verify
```

---

## File Structure

```
auto-approver_aws/
├── aws_complete_setup.sh          # 🎯 Main setup and management script
├── build_push_docker_img.sh       # 🐳 Docker build and push script
├── aws_wrapper.py                 # 🐍 AWS integration wrapper
├── dockerfile                     # 🐳 Container definition
├── requirements_aws.txt           # 📦 Python dependencies
├── test_local.py                  # 🧪 Local testing script
├── .env.aws                       # 🔧 Environment variables (auto-generated)
└── ecs-task-definition-*.json     # 📋 ECS task definitions (auto-generated)
```

---

## Account Configuration

### CSV File Format

The system reads accounts from CSV files in `../auto-approver/`:

- **Production**: `academics_accounts.csv`, `superbuilders_accounts.csv`
- **Testing**: `accounts_test.csv`

**CSV Format:**
```csv
username,password,email,max_approvals,delay_seconds
@username,password123,email@example.com,50,3
```

### Test vs Production Mode

- **Test Mode**: `TEST_MODE=true` → Uses `accounts_test.csv` (1-2 accounts)
- **Production Mode**: `TEST_MODE=false` → Uses all production CSV files (currently 169 accounts)

---

## Usage Guide

### Daily Operation

The system **runs automatically** every day at **9:00 AM UTC**. No manual intervention required.

### Manual Operations

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
./build_push_docker_img.sh
# 3. Test changes
./aws_complete_setup.sh --test
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
  "summary": {
    "total_accounts": 169,
    "successful_accounts": 165,
    "total_approvals": 1247,
    "success_rate": 97.6
  }
}
```

### Log Locations
- **CloudWatch**: `/ecs/twitter-automation`
- **Retention**: 7 days
- **Streams**: `ecs-production/*` and `ecs-test/*`

---

## Cost Analysis

### Monthly Costs (Estimated)

| Component | Specification | Monthly Cost |
|-----------|---------------|--------------|
| **ECS Fargate** | 2 vCPU, 4GB × 2hrs/day × 30 days | **$12.10** |
| **S3 Storage** | ~1GB results/logs | **$0.23** |
| **CloudWatch** | Log storage + dashboard | **$2.00** |
| **Data Transfer** | Minimal | **$1.00** |
| **ECR** | Docker image storage | **$0.50** |
| **Total** |  | **~$15.83/month** |

### Cost Optimization
- **No idle costs**: Only pay when tasks are running
- **Automatic scaling**: Resources allocated only during execution
- **Log retention**: 7 days to control storage costs

---

## Security

### IAM Roles
- **ECS Task Execution Role**: Container management
- **ECS Task Role**: S3 access for results
- **EventBridge Role**: Task scheduling

### Network Security
- **VPC**: Runs in default VPC
- **Security Groups**: Outbound HTTPS/HTTP only
- **No inbound access**: Containers are not accessible from internet

### Credential Management
- **No hardcoded credentials**: Uses IAM roles
- **Account credentials**: Stored in CSV files (should be encrypted at rest)

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails
```bash
# Clear Docker cache and rebuild
docker system prune -f
./build_push_docker_img.sh
```

#### 2. Task Fails to Start
```bash
# Check task definition
aws ecs describe-task-definition --task-definition twitter-automation-test

# Check recent task failures
aws ecs describe-tasks --cluster twitter-automation --include TAGS
```

#### 3. No Follow Requests Approved
- Check if accounts are in allowed usernames list
- Verify account credentials are correct
- Check CloudWatch logs for authentication errors

#### 4. ChromeDriver Issues
The Docker image includes a fixed ChromeDriver version. If Chrome updates:
```bash
# Update dockerfile with new ChromeDriver version
# Rebuild image
./build_push_docker_img.sh
```

### Debug Commands

#### Check Task Status
```bash
# List recent tasks
aws ecs list-tasks --cluster twitter-automation

# Get task details
aws ecs describe-tasks --cluster twitter-automation --tasks TASK_ARN
```

#### Manual Task Execution
```bash
# Run production task manually
aws ecs run-task \
    --cluster twitter-automation \
    --task-definition twitter-automation-production \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Development

### Local Testing
```bash
# Test imports and CSV loading
python3 test_local.py
```

### Adding New Features
1. Modify `aws_wrapper.py` or automation scripts
2. Update `dockerfile` if needed
3. Rebuild image: `./build_push_docker_img.sh`
4. Test: `./aws_complete_setup.sh --test`

### Environment Variables
```bash
# Key environment variables (set in task definition)
TEST_MODE=true|false          # Toggle test vs production
S3_BUCKET_NAME=bucket-name    # Results storage
AWS_DEFAULT_REGION=us-east-1  # AWS region
```

---

## Support

### AWS Console Links
- **ECS Cluster**: https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/twitter-automation
- **CloudWatch Logs**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups
- **EventBridge Rules**: https://console.aws.amazon.com/events/home?region=us-east-1#/rules
- **S3 Bucket**: https://console.aws.amazon.com/s3/buckets/twitter-automation-results

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

#### Complete Cleanup
```bash
# WARNING: This removes all AWS resources
# Use aws_complete_setup.sh --setup to recreate
aws ecs delete-cluster --cluster twitter-automation
aws events delete-rule --name twitter-automation-daily --region us-east-1
aws s3 rb s3://twitter-automation-results --force
```

---

**🎯 System Status**: Ready for daily production use
**📅 Next Run**: Every day at 9:00 AM UTC
**📊 Accounts**: 169 total (131 academics + 38 superbuilders)
**⏱️ Duration**: ~2 hours per run
**💰 Cost**: ~$16/month
```

This comprehensive README.md provides everything needed to understand, deploy, operate, and maintain the AWS Twitter automation system.
