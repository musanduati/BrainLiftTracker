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