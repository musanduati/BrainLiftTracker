# Register test task definition
aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition-test.json \
    --region us-east-1

# Load environment variables
source .env.aws

# Run test task
echo "🧪 Starting TEST ECS task..."

TASK_ARN=$(aws ecs run-task \
    --cluster twitter-automation \
    --task-definition twitter-automation-test \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
    --region us-east-1 \
    --query "tasks[0].taskArn" --output text)

echo "🧪 Test task started: $TASK_ARN"

# Monitor the task
for i in {1..8}; do
    STATUS=$(aws ecs describe-tasks \
        --cluster twitter-automation \
        --tasks $TASK_ARN \
        --query "tasks[0].lastStatus" --output text)
    
    echo "[$i/8] Test task status: $STATUS"
    
    if [ "$STATUS" = "STOPPED" ]; then
        echo "✅ Test task completed!"
        break
    fi
    
    sleep 30
done

echo "✅ Test run completed"

# Check logs to see if ChromeDriver was downloaded correctly
echo "📋 Checking CloudWatch logs for ChromeDriver setup..."

sleep 30

LOG_STREAM=$(aws logs describe-log-streams \
    --log-group-name /ecs/twitter-automation \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --query "logStreams[0].logStreamName" --output text)

echo "Latest log stream: $LOG_STREAM"

if [ "$LOG_STREAM" != "None" ] && [ "$LOG_STREAM" != "" ]; then
    echo "📖 Recent log events:"
    aws logs get-log-events \
        --log-group-name /ecs/twitter-automation \
        --log-stream-name $LOG_STREAM \
        --start-from-head \
        --limit 30 \
        --query "events[*].message" \
        --output text
fi