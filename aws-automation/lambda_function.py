"""
AWS Lambda Function for Twitter Thread Automation

This function runs every hour via EventBridge and calls the 
Lightsail API to post pending threads and retry failed threads.
"""

import json
import boto3
import requests
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
ssm = boto3.client('ssm')
cloudwatch = boto3.client('cloudwatch')

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
            '/twitter-automation/api-url',
            '/twitter-automation/api-key',
            '/twitter-automation/max-threads-per-run',
            '/twitter-automation/delay-between-threads',
            '/twitter-automation/timeout-seconds'
        ]
        
        response = ssm.get_parameters(
            Names=parameters,
            WithDecryption=True
        )
        
        # Build config dict
        config = {}
        for param in response['Parameters']:
            key = param['Name'].split('/')[-1].replace('-', '_')
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