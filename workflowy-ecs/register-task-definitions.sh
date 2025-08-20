#!/bin/bash

set -e

echo "📋 Registering ECS Task Definitions..."

# Check if task definition files exist
if [ ! -f "ecs-task-definition-workflowy-test.json" ]; then
    echo "❌ Test task definition not found. Generate with: ./setup-workflowy-complete.sh --generate-tasks"
    exit 1
fi

if [ ! -f "ecs-task-definition-workflowy-production.json" ]; then
    echo "❌ Production task definition not found. Generate with: ./setup-workflowy-complete.sh --generate-tasks"
    exit 1
fi

# Register test task definition
echo "🧪 Registering test task definition..."
TEST_REVISION=$(aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition-workflowy-test.json \
    --region us-east-1 \
    --query 'taskDefinition.revision' \
    --output text)

echo "✅ Test task definition registered as revision: $TEST_REVISION"

# Register production task definition  
echo "🚀 Registering production task definition..."
PROD_REVISION=$(aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition-workflowy-production.json \
    --region us-east-1 \
    --query 'taskDefinition.revision' \
    --output text)

echo "✅ Production task definition registered as revision: $PROD_REVISION"

echo "📊 Current active task definitions:"
aws ecs list-task-definitions \
    --family-prefix workflowy-processor \
    --status ACTIVE \
    --region us-east-1 \
    --query 'taskDefinitionArns' \
    --output table

echo "✅ Task definition registration completed!"
echo "🧪 Test with: ./run-workflowy-test.sh"
