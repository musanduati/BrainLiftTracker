#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import datetime

def load_api_secrets():
    """Load API keys from single Secrets Manager secret and save to environment variables"""
    try:
        # Get the JSON string that ECS injected from Secrets Manager
        secrets_json = os.getenv('BRAINLIFT_TRACKER')
        if not secrets_json:
            structured_logger.warning_operation("load_api_secrets", "⚠️ No secrets found in BRAINLIFT_TRACKER environment variable")
            return {}
 
        secrets = json.loads(secrets_json)
        structured_logger.info_operation("load_api_secrets", f"✅ Loaded {len(secrets)} secrets from Secrets Manager")
        
        secrets_loaded = 0
        
        if 'API_BASE' in secrets:
            os.environ['API_BASE'] = secrets['API_BASE']
            structured_logger.info_operation("load_api_secrets", f"✅ API_BASE loaded ({secrets['API_BASE'][:15]}...)")
            secrets_loaded += 1
        
        if 'API_KEY' in secrets:
            os.environ['API_KEY'] = secrets['API_KEY']
            structured_logger.info_operation("load_api_secrets", f"✅ API_KEY loaded ({secrets['API_KEY'][:15]}...)")
            secrets_loaded += 1

        if 'OPENAI_API_KEY' in secrets:
            os.environ['OPENAI_API_KEY'] = secrets['OPENAI_API_KEY']
            structured_logger.info_operation("load_api_secrets", f"✅ OPENAI_API_KEY loaded ({secrets['OPENAI_API_KEY'][:15]}...)")
            secrets_loaded += 1
        
        structured_logger.info_operation("load_api_secrets", f"🔐 Total secrets loaded: {secrets_loaded}")
        return secrets
        
    except json.JSONDecodeError as e:
        structured_logger.error_operation("load_api_secrets", f"❌ Failed to parse secrets JSON: {e}")
        structured_logger.error_operation("load_api_secrets", f"Raw value: {secrets_json[:100]}...")
        return {}
    except Exception as e:
        structured_logger.error_operation("load_api_secrets", f"❌ Failed to load secrets from Secrets Manager: {e}")
        return {}

# Configure logging for ECS before importing workflowy modules
def configure_ecs_logging():
    """Configure structured logging for ECS environment"""
    from workflowy.config.logger import LogContext
    return LogContext

# Now configure logging
LogContext = configure_ecs_logging()
from workflowy.config.logger import structured_logger

structured_logger.info_operation("ecs_workflowy_processor", "🔐 Loading secrets before module imports...")
api_secrets = load_api_secrets()

from workflowy.lambda_handler import process_and_post_v2

class ECSWorkflowyProcessor:
    def __init__(self):
        # Set up logging context
        import uuid
        self.request_id = str(uuid.uuid4())
        LogContext.set_request_id(self.request_id)
        LogContext.set_operation("ecs_workflowy_processor")
        
        self.environment = os.getenv('ENVIRONMENT', 'test')
        self.start_time = datetime.now()
        
        # Log startup info
        structured_logger.info_operation("ecs_init", "🚀 Workflowy ECS processor initialized", 
                                        environment=self.environment,
                                        execution_env="AWS_ECS_FARGATE",
                                        request_id=self.request_id,
                                        secrets_loaded=len(api_secrets))
        
    async def run_workflowy_processing(self):
        structured_logger.info_operation("ecs_processor", f"🚀 Starting Workflowy processor in ECS Fargate (environment: {self.environment})")
        
        try:
            results = await process_and_post_v2(self.environment)

            processing_successful = len([r for r in results['processing_results'] if r['status'] == 'success'])
            processing_failed = len([r for r in results['processing_results'] if r['status'] == 'error'])
            posting_successful = len([r for r in results['posting_results'] if r['status'] == 'success'])
            posting_failed = len([r for r in results['posting_results'] if r['status'] == 'error'])
            
            structured_logger.info_operation("run_workflowy_processing", f"✅ Processing complete: {processing_successful} successful, {processing_failed} failed")
            structured_logger.info_operation("run_workflowy_processing", f"✅ Posting complete: {posting_successful} successful, {posting_failed} failed")
            
            return {
                'statusCode': 200,
                'body': json.dumps(results, default=str)
            }
            
        except Exception as e:
            structured_logger.error_operation("run_workflowy_processing", f"❌ ECS task failed")
            raise

def main():
    """Main entry point"""
    processor = ECSWorkflowyProcessor()
    
    try:
        # Run async processing
        result = asyncio.run(processor.run_workflowy_processing())
        structured_logger.info_operation("ecs_main", f"🔐 Result: {result}")
        duration = (datetime.now() - processor.start_time).total_seconds()
        duration_minutes = duration / 60
        structured_logger.info_operation("ecs_main", f"✅ Workflowy processing completed successfully in {duration_minutes:.2f} minutes ({duration:.2f} seconds)")
        exit(0)
    except Exception as e:
        structured_logger.error_operation("ecs_main", e, f"❌ Workflowy processing failed")
        exit(1)

if __name__ == "__main__":
    main()
