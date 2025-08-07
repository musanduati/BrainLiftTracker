#!/usr/bin/env python3
"""
Local test script to mimic Lambda execution for Project-based System V2
Supports testing:
1. Regular project-based Workflowy processing + tweet posting (default)
2. Project-based bulk URL processing (creates projects with project_ids)
3. Single project testing
"""

import sys
import json
import argparse
from pathlib import Path
from logger_config import logger

# Add the workflowy directory to Python path
workflowy_dir = Path(__file__).parent / "workflowy"
sys.path.insert(0, str(workflowy_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import the V2 lambda handler
from lambda_handler_v2 import lambda_handler

def create_mock_lambda_context():
    """Create a mock Lambda context object"""
    class MockContext:
        def __init__(self):
            self.function_name = "workflowy-processor-v2"
            self.function_version = "$LATEST"
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:workflowy-processor-v2"
            self.memory_limit_in_mb = "512"
            self.remaining_time_in_millis = lambda: 300000  # 5 minutes
            self.log_group_name = "/aws/lambda/workflowy-processor-v2"
            self.log_stream_name = "2024/01/01/[$LATEST]abc123"
            self.aws_request_id = "local-test-v2-12345"

    return MockContext()

def create_scheduled_event():
    """Create a mock scheduled event for regular project processing"""
    return {
        "source": "aws.events",
        "detail-type": "Scheduled Event - V2",
        "time": "2024-01-01T12:00:00Z",
        "environment": "test"
    }

def create_bulk_url_event():
    """Create a mock event with bulk URL data for project creation"""
    return {
        "body": json.dumps([
            {
                "brainlift": "https://workflowy.com/s/test-project-1/abc123xyz",
                "account_id": "1",
                "name": "Test Project 1"
            },
            {
                "brainlift": "https://workflowy.com/s/test-project-2/def456uvw",
                "account_id": "2", 
                "name": "Test Project 2"
            }
        ]),
        "headers": {
            "Content-Type": "application/json"
        },
        "environment": "test"
    }

def create_custom_bulk_url_event(custom_file: str):
    """Create a mock event with custom bulk URL data"""
    try:
        file_path = Path(custom_file)
        if not file_path.exists():
            logger.error(f"❌ Custom file not found: {custom_file}")
            return None
        
        with open(file_path, 'r') as f:
            bulk_data = json.load(f)
        
        logger.info(f"📁 Loaded {len(bulk_data)} URL entries from {custom_file}")
        
        return {
            "body": json.dumps(bulk_data),
            "headers": {
                "Content-Type": "application/json"
            },
            "environment": "test"
        }
    except Exception as e:
        logger.error(f"❌ Error loading custom file {custom_file}: {e}")
        return None

def create_single_project_event(project_id: str):
    """Create a mock event for testing a single project"""
    return {
        "source": "manual.test",
        "detail-type": "Single Project Test",
        "time": "2024-01-01T12:00:00Z",
        "environment": "test",
        "project_id": project_id
    }

def display_posting_results(result):
    """Display results from regular project posting"""
    logger.info("📊 PROJECT POSTING RESULTS:")
    logger.info("-" * 40)
    
    if isinstance(result, dict):
        # Handle V2 lambda response format (no HTTP wrapper)
        if 'processing_results' in result and 'posting_results' in result:
            processing_results = result.get('processing_results', [])
            posting_results = result.get('posting_results', [])
            
            # Calculate summary statistics
            total_projects = len(processing_results)
            successful_projects = len([r for r in processing_results if r.get('status') == 'success'])
            failed_projects = total_projects - successful_projects
            
            total_tweets_posted = sum(r.get('posted_tweets', 0) for r in posting_results)
            total_tweets_failed = sum(r.get('failed_tweets', 0) for r in posting_results)
            
            logger.info(f"Status: Success")
            logger.info(f"Environment: {result.get('environment', 'test')}")
            logger.info(f"Projects Processed: {total_projects}")
            logger.info(f"Successful Projects: {successful_projects}")
            logger.info(f"Failed Projects: {failed_projects}")
            logger.info(f"Total Tweets Posted: {total_tweets_posted}")
            logger.info(f"Total Tweets Failed: {total_tweets_failed}")
            
            # Show individual project results
            if processing_results:
                logger.info("📋 Individual Project Results:")
                for i, result in enumerate(processing_results):
                    project_id = result.get('project_id', 'Unknown')
                    status = result.get('status', 'Unknown')
                    project_name = result.get('project_name', 'Unknown')
                    
                    if status == 'success':
                        dok4_points = result.get('dok4_points', 0)
                        dok3_points = result.get('dok3_points', 0)
                        total_change_tweets = result.get('total_change_tweets', 0)
                        first_run = result.get('first_run', False)
                        
                        logger.info(f"  ✅ {project_name} ({project_id})")
                        logger.info(f"     DOK4: {dok4_points} points, DOK3: {dok3_points} points")
                        logger.info(f"     Change tweets: {total_change_tweets}, First run: {first_run}")
                    else:
                        error = result.get('error', 'Unknown error')
                        logger.info(f"  ❌ {project_name} ({project_id}): {error}")
                
                # Show posting results
                if posting_results and posting_results[0].get('project_id') != 'none':
                    logger.info("\n🐦 Tweet Posting Results:")
                    for result in posting_results:
                        project_id = result.get('project_id', 'Unknown')
                        status = result.get('status', 'Unknown')
                        
                        if status == 'success':
                            posted = result.get('posted_tweets', 0)
                            failed = result.get('failed_tweets', 0)
                            total = result.get('total_tweets', 0)
                            logger.info(f"  🐦 {project_id}: {posted}/{total} posted, {failed} failed")
                        else:
                            error = result.get('error', 'Unknown error')
                            logger.info(f"  ❌ {project_id}: {error}")
        
        # Handle HTTP response format
        elif 'statusCode' in result:
            logger.info(f"Status Code: {result.get('statusCode', 'Unknown')}")
            
            body = result.get('body', '{}')
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except:
                    pass
            
            if isinstance(body, dict):
                # Check if this is the new V2 format with 'processing' and 'posting' objects
                if 'processing' in body and 'posting' in body:
                    processing = body.get('processing', {})
                    posting = body.get('posting', {})
                    
                    processing_results = processing.get('results', [])
                    posting_results = posting.get('results', [])
                    
                    # Calculate summary statistics
                    total_projects = processing.get('total_processed', 0)
                    successful_projects = processing.get('successful', 0)
                    failed_projects = processing.get('failed', 0)
                    
                    total_tweets_posted = sum(r.get('posted_tweets', 0) for r in posting_results)
                    total_tweets_failed = sum(r.get('failed_tweets', 0) for r in posting_results)
                    
                    logger.info(f"Operation: Project-based Processing + Tweet Posting (V2)")
                    logger.info(f"Environment: {body.get('environment', 'Unknown')}")
                    logger.info(f"Projects Processed: {total_projects}")
                    logger.info(f"Total Tweets Posted: {total_tweets_posted}")
                    logger.info(f"Total Tweets Failed: {total_tweets_failed}")
                    
                    # Show individual project results
                    if processing_results:
                        logger.info("📋 Individual Project Results:")
                        for i, result in enumerate(processing_results):
                            project_id = result.get('project_id', 'Unknown')
                            status = result.get('status', 'Unknown')
                            project_name = result.get('project_name', 'Unknown')
                            
                            if status == 'success':
                                dok4_points = result.get('dok4_points', 0)
                                dok3_points = result.get('dok3_points', 0)
                                total_change_tweets = result.get('total_change_tweets', 0)
                                first_run = result.get('first_run', False)
                                
                                logger.info(f"  ✅ {project_name} ({project_id})")
                                logger.info(f"     DOK4: {dok4_points} points, DOK3: {dok3_points} points")
                                logger.info(f"     Change tweets: {total_change_tweets}, First run: {first_run}")
                            else:
                                error = result.get('error', 'Unknown error')
                                logger.info(f"  ❌ {project_name} ({project_id}): {error}")
                        
                        # Show posting results
                        if posting_results and posting_results[0].get('project_id') != 'none':
                            logger.info("🐦 Tweet Posting Results:")
                            for result in posting_results:
                                project_id = result.get('project_id', 'Unknown')
                                status = result.get('status', 'Unknown')
                                
                                if status == 'success':
                                    posted = result.get('posted_tweets', 0)
                                    failed = result.get('failed_tweets', 0)
                                    total = result.get('total_tweets', 0)
                                    logger.info(f"  🐦 {project_id}: {posted}/{total} posted, {failed} failed")
                                else:
                                    error = result.get('error', 'Unknown error')
                                    logger.info(f"  ❌ {project_id}: {error}")
                else:
                    # Legacy format handling
                    logger.info(f"Operation: {body.get('operation', 'Unknown')}")
                    logger.info(f"Environment: {body.get('environment', 'Unknown')}")
                    logger.info(f"Projects Processed: {body.get('projects_processed', 0)}")
                    logger.info(f"Total Tweets Posted: {body.get('total_tweets_posted', 0)}")
                    logger.info(f"Total Tweets Failed: {body.get('total_tweets_failed', 0)}")
            else:
                logger.info(f"Response Body: {body}")
        else:
            logger.info(f"Unknown result format: {result}")
    else:
        logger.error(f"Unexpected result format: {result}")

def display_bulk_url_results(result):
    """Display results from bulk URL processing"""
    logger.info("📊 BULK URL PROCESSING RESULTS:")
    logger.info("-" * 40)
    
    if isinstance(result, dict):
        logger.info(f"Status Code: {result.get('statusCode', 'Unknown')}")
        
        body = result.get('body', '{}')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except:
                pass
        
        if isinstance(body, dict):
            logger.info(f"Operation: {body.get('operation', 'Unknown')}")
            logger.info(f"Environment: {body.get('environment', 'Unknown')}")
            logger.info(f"Total Processed: {body.get('total_processed', 0)}")
            logger.info(f"Successful: {body.get('successful', 0)}")
            logger.info(f"Failed: {body.get('failed', 0)}")
            
            # Show successful projects
            successful_projects = body.get('successful_projects', [])
            if successful_projects:
                logger.info("✅ Successfully Created Projects:")
                for project in successful_projects:
                    project_id = project.get('project_id', 'Unknown')
                    name = project.get('name', 'Unknown')
                    account_id = project.get('account_id', 'Unknown')
                    logger.info(f"  • {project_id} - {name} (Account: {account_id})")
            
            # Show failed projects
            failed_projects = body.get('failed_projects', [])
            if failed_projects:
                logger.info("❌ Failed Projects:")
                for project in failed_projects:
                    url = project.get('url', 'Unknown')
                    error = project.get('error', 'Unknown error')
                    logger.info(f"  • {url}: {error}")
                    
            # Show validation results
            validation = body.get('validation', {})
            if validation:
                logger.info(f"\n📋 Validation: {validation.get('valid_entries', 0)} valid, {validation.get('invalid_entries', 0)} invalid")
        else:
            logger.info(f"Response Body: {body}")
    else:
        logger.error(f"Unexpected result format: {result}")

def display_single_project_results(result):
    """Display results from single project testing"""
    logger.info("📊 SINGLE PROJECT TEST RESULTS:")
    logger.info("-" * 40)
    
    if isinstance(result, dict):
        logger.info(f"Status Code: {result.get('statusCode', 'Unknown')}")
        
        body = result.get('body', '{}')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except:
                pass
        
        if isinstance(body, dict):
            project_id = body.get('project_id', 'Unknown')
            status = body.get('status', 'Unknown')
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Status: {status}")
            
            if status == 'success':
                logger.info(f"Project Name: {body.get('project_name', 'Unknown')}")
                logger.info(f"Account ID: {body.get('account_id', 'Unknown')}")
                logger.info(f"First Run: {body.get('first_run', 'Unknown')}")
                logger.info(f"Total Change Tweets: {body.get('total_change_tweets', 0)}")
                logger.info(f"DOK4 Points: {body.get('dok4_points', 0)}")
                logger.info(f"DOK3 Points: {body.get('dok3_points', 0)}")
                
                if body.get('content_url'):
                    logger.info(f"Content URL: {body.get('content_url')}")
                if body.get('tweets_url'):
                    logger.info(f"Tweets URL: {body.get('tweets_url')}")
            else:
                logger.info(f"Error: {body.get('error', 'Unknown error')}")
        else:
            logger.info(f"Response Body: {body}")
    else:
        logger.error(f"Unexpected result format: {result}")

def main():
    """Main function to test Lambda V2 locally"""
    parser = argparse.ArgumentParser(description="Test Workflowy Lambda V2 function locally")
    parser.add_argument(
        "mode", 
        choices=["posting", "bulk", "project"],
        nargs="?",
        default=None,
        help="Test mode: posting (default), bulk, project"
    )
    parser.add_argument(
        "--custom-file",
        type=str,
        help="Path to custom JSON file with bulk URLs (for bulk mode)"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        help="Specific project ID to test (for project mode)"
    )
    parser.add_argument(
        "--environment",
        type=str,
        default="test",
        help="Environment to test (test, staging, production)"
    )
    
    args = parser.parse_args()

    # Error out if no mode is provided
    if args.mode is None:
        logger.error("❌ No mode provided. Please specify 'posting', 'bulk', or 'project' mode.")
        return 1
    
    logger.info("🏠 Running Lambda V2 function locally...")
    logger.info(f"🌍 Environment: {args.environment}")
    logger.info("="*50)
    
    # Create appropriate event based on mode
    if args.mode == "posting":
        logger.info("🔄 Testing REGULAR project-based Workflowy processing + tweet posting...")
        mock_event = create_scheduled_event()
        mock_event["environment"] = args.environment
        
    elif args.mode == "bulk":
        if args.custom_file:
            logger.info(f"🔗 Testing BULK URL processing with custom file: {args.custom_file}...")
            mock_event = create_custom_bulk_url_event(args.custom_file)
            if mock_event is None:
                return 1
        else:
            logger.info("🔗 Testing BULK URL processing with default test data...")
            mock_event = create_bulk_url_event()
        mock_event["environment"] = args.environment
        
    elif args.mode == "project":
        if not args.project_id:
            logger.error("❌ Project mode requires --project-id argument")
            return 1
        logger.info(f"🎯 Testing SINGLE PROJECT: {args.project_id}...")
        mock_event = create_single_project_event(args.project_id)
        mock_event["environment"] = args.environment
        
    else:
        logger.error("❌ Invalid mode. Please specify 'posting', 'bulk', or 'project'.")
        return 1
    
    mock_context = create_mock_lambda_context()
    
    try:
        # Call the lambda handler V2
        result = lambda_handler(mock_event, mock_context)
        
        logger.info("="*50)
        logger.info("✅ Lambda V2 execution completed successfully!")
        logger.info("="*50)
        
        # Display results based on mode
        if args.mode == "posting":
            display_posting_results(result)
        elif args.mode == "bulk":
            display_bulk_url_results(result)
        elif args.mode == "project":
            display_single_project_results(result)
            
    except Exception as e:
        logger.error(f"❌ Lambda V2 execution failed!")
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    logger.info("🧪 Workflowy Lambda V2 Local Tester")
    logger.info("Available modes:")
    logger.info("  posting      - Test regular project-based Workflowy processing + tweet posting")
    logger.info("  bulk         - Test bulk URL processing to create projects")
    logger.info("  project      - Test single project processing")
    logger.info("Usage examples:")
    logger.info("  python test_lambda_local_v2.py posting")
    logger.info("  python test_lambda_local_v2.py bulk --custom-file test_bulk_url_upload.json")
    logger.info("  python test_lambda_local_v2.py project --project-id project_abc123")
    logger.info("  python test_lambda_local_v2.py posting --environment staging")
    
    exit_code = main()
    sys.exit(exit_code) 