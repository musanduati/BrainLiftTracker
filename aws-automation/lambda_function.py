"""
AWS Lambda Function for Twitter Thread Automation

This function runs every hour via EventBridge and calls the 
Lightsail API to post pending threads and retry failed threads.
"""

import json
import boto3
import requests
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
ssm = boto3.client('ssm')
cloudwatch = boto3.client('cloudwatch')
s3 = boto3.client('s3')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for thread automation
    
    Args:
        event: EventBridge event data
        context: Lambda context
        
    Returns:
        Dict with execution results
    """
    execution_id = f"exec_{int(datetime.utcnow().timestamp())}"
    
    try:
        logger.info(f"Starting thread automation execution: {execution_id}")
        
        # Get configuration from SSM Parameter Store
        config = get_automation_config()
        
        # Validate configuration
        if not validate_config(config):
            raise ValueError("Invalid configuration")
        
        # Call automation endpoint
        automation_result = call_automation_endpoint(config)
        
        # Add Lambda request ID for tracking
        automation_result['lambda_request_id'] = context.aws_request_id if context else None
        
        # Upload report to S3
        s3_url = upload_report_to_s3(automation_result, config)
        if s3_url:
            automation_result['report_s3_url'] = s3_url
        
        # Send metrics to CloudWatch
        send_cloudwatch_metrics(automation_result)
        
        # Prepare response
        response = {
            'statusCode': 200,
            'execution_id': execution_id,
            'timestamp': datetime.utcnow().isoformat(),
            'automation_result': automation_result,
            'success': True
        }
        
        logger.info(f"Automation completed successfully: {execution_id}")
        logger.info(f"Summary: {automation_result.get('summary', {})}")
        
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Automation failed: {error_msg}")
        
        # Send error metrics
        send_error_metrics(error_msg)
        
        # Return error response
        return {
            'statusCode': 500,
            'execution_id': execution_id,
            'timestamp': datetime.utcnow().isoformat(),
            'error': error_msg,
            'success': False
        }

def get_automation_config() -> Dict[str, Any]:
    """
    Retrieve automation configuration from SSM Parameter Store
    
    Returns:
        Dict with configuration parameters
    """
    try:
        # Get parameters from SSM
        parameters = [
            'twitter.automation.api.url',
            'twitter.automation.api.key',
            'twitter.automation.max.threads.per.run',
            'twitter.automation.delay.between.threads',
            'twitter.automation.timeout.seconds',
            'twitter.automation.s3.bucket.name'
        ]
        
        response = ssm.get_parameters(
            Names=parameters,
            WithDecryption=True
        )
        
        # Build config dict
        config = {}
        for param in response['Parameters']:
            # Extract key from dot notation (e.g., 'twitter.automation.api.url' -> 'api_url')
            key_parts = param['Name'].split('.')
            key = '_'.join(key_parts[2:])  # Skip 'twitter.automation' prefix
            value = param['Value']
            
            # Convert numeric values
            if key in ['max_threads_per_run', 'delay_between_threads', 'timeout_seconds']:
                value = int(value)
                
            config[key] = value
        
        # Set defaults for missing parameters
        config.setdefault('max_threads_per_run', 10)
        config.setdefault('delay_between_threads', 5)
        config.setdefault('timeout_seconds', 300)
        config.setdefault('post_pending', True)
        config.setdefault('retry_failed', True)
        config.setdefault('dry_run', False)
        
        logger.info("Configuration loaded from SSM Parameter Store")
        return config
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise

def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate automation configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_keys = ['api_url', 'api_key']
    
    for key in required_keys:
        if key not in config or not config[key]:
            logger.error(f"Missing required configuration: {key}")
            return False
    
    return True

def call_automation_endpoint(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call the Lightsail automation endpoint
    
    Args:
        config: Configuration dictionary
        
    Returns:
        API response data
    """
    url = f"{config['api_url'].rstrip('/')}/api/v1/threads/automation/run"
    
    headers = {
        'X-API-Key': config['api_key'],
        'Content-Type': 'application/json',
        'User-Agent': 'AWS-Lambda-Thread-Automation/1.0'
    }
    
    payload = {
        'max_threads_per_run': config['max_threads_per_run'],
        'delay_between_threads': config['delay_between_threads'],
        'post_pending': config['post_pending'],
        'retry_failed': config['retry_failed'],
        'dry_run': config['dry_run']
    }
    
    logger.info(f"Calling automation endpoint: {url}")
    logger.info(f"Payload: {payload}")
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config['timeout_seconds']
        )
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"API call successful: {response.status_code}")
        logger.info(f"Automation status: {result.get('status', 'unknown')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API response: {str(e)}")
        raise

def upload_report_to_s3(automation_result: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
    """Upload automation report to S3 bucket"""
    try:
        bucket_name = config.get('s3_bucket_name')
        if not bucket_name:
            logger.warning("S3 bucket not configured, skipping report upload")
            return None
            
        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
        execution_id = automation_result.get('automation_id', str(uuid.uuid4())[:8])
        filename = f"automation-reports/{timestamp}_{execution_id}_report.json"
        
        # Prepare comprehensive report
        report = {
            "metadata": {
                "timestamp": timestamp,
                "execution_id": execution_id,
                "lambda_request_id": automation_result.get('lambda_request_id'),
                "report_version": "1.0"
            },
            "automation_result": automation_result,
            "configuration": {
                "max_threads_per_run": config.get('max_threads_per_run'),
                "delay_between_threads": config.get('delay_between_threads'),
                "api_url": config.get('api_url', '').replace('api-key', '***'),  # Redact sensitive info
                "dry_run": config.get('dry_run', False)
            }
        }
        
        # Upload to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=json.dumps(report, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'execution-id': execution_id,
                'timestamp': timestamp,
                'status': automation_result.get('status', 'unknown')
            }
        )
        
        s3_url = f"s3://{bucket_name}/{filename}"
        logger.info(f"Report uploaded to S3: {s3_url}")
        return s3_url
        
    except Exception as e:
        logger.error(f"Failed to upload report to S3: {str(e)}")
        return None

def send_cloudwatch_metrics(automation_result: Dict[str, Any]) -> None:
    """
    Send automation metrics to CloudWatch
    
    Args:
        automation_result: Result from automation endpoint
    """
    try:
        metrics = []
        summary = automation_result.get('summary', {})
        
        # Basic metrics
        metrics.extend([
            {
                'MetricName': 'AutomationExecutions',
                'Value': 1,
                'Unit': 'Count'
            },
            {
                'MetricName': 'ThreadsProcessed',
                'Value': summary.get('total_threads_processed', 0),
                'Unit': 'Count'
            },
            {
                'MetricName': 'TweetsPosted',
                'Value': summary.get('total_tweets_posted', 0),
                'Unit': 'Count'
            },
            {
                'MetricName': 'TweetFailures',
                'Value': summary.get('total_failures', 0),
                'Unit': 'Count'
            },
            {
                'MetricName': 'OperationsCompleted',
                'Value': summary.get('operations_completed', 0),
                'Unit': 'Count'
            },
            {
                'MetricName': 'ExecutionTime',
                'Value': automation_result.get('execution_time_seconds', 0),
                'Unit': 'Seconds'
            }
        ])
        
        # Additional metrics for single tweets (if available)
        pending_op = automation_result.get('results', {}).get('pending_operation', {})
        if 'single_tweets_processed' in pending_op:
            metrics.append({
                'MetricName': 'SingleTweetsProcessed',
                'Value': pending_op.get('single_tweets_processed', 0),
                'Unit': 'Count'
            })
        
        # Status-based metrics
        status = automation_result.get('status', 'unknown')
        metrics.append({
            'MetricName': f'Status_{status.title()}',
            'Value': 1,
            'Unit': 'Count'
        })
        
        # Send metrics
        cloudwatch.put_metric_data(
            Namespace='TwitterAutomation',
            MetricData=metrics
        )
        
        logger.info(f"Sent {len(metrics)} metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Failed to send CloudWatch metrics: {str(e)}")
        # Don't raise - metrics failure shouldn't fail the automation

def send_error_metrics(error_message: str) -> None:
    """
    Send error metrics to CloudWatch
    
    Args:
        error_message: Error message
    """
    try:
        cloudwatch.put_metric_data(
            Namespace='TwitterAutomation',
            MetricData=[
                {
                    'MetricName': 'AutomationErrors',
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'Status_Error',
                    'Value': 1,
                    'Unit': 'Count'
                }
            ]
        )
        
        logger.info("Sent error metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Failed to send error metrics: {str(e)}")

# Optional: SNS notification function
def send_notification(subject: str, message: str, config: Dict[str, Any]) -> None:
    """
    Send SNS notification (optional feature)
    
    Args:
        subject: Notification subject
        message: Notification message
        config: Configuration dictionary
    """
    try:
        sns_topic = config.get('sns_topic_arn')
        if not sns_topic:
            return
        
        sns = boto3.client('sns')
        sns.publish(
            TopicArn=sns_topic,
            Subject=subject,
            Message=message
        )
        
        logger.info("Sent SNS notification")
        
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")