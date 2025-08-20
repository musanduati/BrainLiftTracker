#!/bin/bash

# Load environment variables
source .env.aws

echo "🧪 Starting Workflowy processor in dedicated cluster..."

TASK_ARN=$(aws ecs run-task \
    --cluster workflowy-processor-cluster \
    --task-definition workflowy-processor-test \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
    --region us-east-1 \
    --query "tasks[0].taskArn" --output text)

echo "✅ Workflowy task started: $TASK_ARN"
echo "📊 Monitor at: https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/workflowy-processor-cluster"

# Monitor the task (it might run for a long time now!)
for i in {1..15}; do
    STATUS=$(aws ecs describe-tasks \
        --cluster workflowy-processor-cluster \
        --tasks $TASK_ARN \
        --query "tasks[0].lastStatus" --output text)
    
    echo "[$i/15] Workflowy task status: $STATUS"
    
    if [ "$STATUS" = "STOPPED" ]; then
        echo "✅ Workflowy task completed!"
        break
    fi
    
    sleep 5 # Check every 5 seconds
done

echo "✅ Workflowy task run completed"
