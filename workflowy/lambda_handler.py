"""
Lambda Handler V2 - Project-based Processing
Updated to use project-based identification instead of user-based identification.
Supports both bulk URL processing and scheduled content processing.
"""

import json
import asyncio
import os
from workflowy.core.workflowy_scraper import WorkflowyTesterV2
from workflowy.core.tweet_poster import TweetPosterV2
from workflowy.storage.aws_storage import AWSStorageV2
from workflowy.core.bulk_processor import is_bulk_url_request_v2, handle_bulk_url_processing_v2
from workflowy.config.logger import logger, structured_logger, LogContext
from workflowy.core.parallel_processor import process_projects_in_batches


def lambda_handler(event, context):
    """
    Lambda handler V2 for:
    1. Bulk URL processing (when event contains brainlift URLs)
    2. Scheduled project processing AND tweet posting (default behavior)
    """
    
    # Set correlation ID from Lambda context
    LogContext.set_request_id(context.aws_request_id)
    LogContext.set_operation("lambda_handler")
    
    # Determine environment from event or context
    environment = os.getenv('ENVIRONMENT', 'test')
    
    # Check if this is a bulk URL processing request
    if is_bulk_url_request_v2(event):
        structured_logger.info_operation("lambda_handler", "🔗 Processing bulk URL upload request (V2)")
        return handle_bulk_url_processing_v2(event, environment)
    else:
        structured_logger.info_operation("lambda_handler", "🚀 Starting project-based processing + Tweet posting in Lambda", environment=environment)
        
        # Run the async processing (updated for project-based approach)
        results = asyncio.run(process_and_post_v2(environment))
        
        scraping_successful = len([r for r in results['processing_results'] if r['status'] == 'success'])
        scraping_failed = len([r for r in results['processing_results'] if r['status'] == 'error'])
        
        posting_successful = len([r for r in results['posting_results'] if r['status'] == 'success'])
        posting_failed = len([r for r in results['posting_results'] if r['status'] == 'error'])
        
        summary = {
            'environment': environment,
            'processing': {
                'total_processed': len(results['processing_results']),
                'successful': scraping_successful,
                'failed': scraping_failed,
                'results': results['processing_results']
            },
            'posting': {
                'total_processed': len(results['posting_results']),
                'successful': posting_successful,
                'failed': posting_failed,
                'results': results['posting_results']
            }
        }
        
        structured_logger.info_operation("lambda_handler", f"✅ Processing complete: {scraping_successful} successful, {scraping_failed} failed", 
                                       successful=scraping_successful, failed=scraping_failed)
        structured_logger.info_operation("lambda_handler", f"✅ Tweet creation complete: {posting_successful} successful, {posting_failed} failed",
                                       successful=posting_successful, failed=posting_failed)
        
        return {
            'statusCode': 200,
            'body': json.dumps(summary, default=str)
        }


async def process_and_post_v2(environment: str = 'test'):
    """Process all projects and then post tweets (project-based approach)."""
    
    # Step 1: Get active projects from DynamoDB
    structured_logger.info_operation("process_and_post_v2", "📊 STEP 1: Loading active projects from DynamoDB...")
    storage = AWSStorageV2(environment)
    projects = storage.get_all_projects()
    
    if not projects:
        structured_logger.error_operation("process_and_post_v2", "❌ No active projects found in DynamoDB!")
        return {
            'processing_results': [{
                'status': 'error',
                'error': 'No active projects configured in DynamoDB'
            }],
            'posting_results': []
        }
    
    # Step 2: Process Workflowy content (OPTIMIZED or ORIGINAL based on config)
    enable_parallel = os.getenv('WORKFLOWY_ENABLE_PARALLEL_PROCESSING', 'false').lower() == 'true'
    
    if enable_parallel:
        structured_logger.info_operation("process_and_post_v2", "📊 STEP 2: Processing Workflowy content (PARALLEL MODE)...")
        batch_size = int(os.getenv('WORKFLOWY_BATCH_SIZE', '10'))
        delay_between_batches = float(os.getenv('WORKFLOWY_DELAY_BETWEEN_BATCHES', '1.0'))
        
        structured_logger.info_operation("process_and_post_v2", f"🔧 Parallel config: batch_size={batch_size}, delay={delay_between_batches}s")
        
        processing_results = await process_projects_in_batches(
            projects, environment, batch_size, delay_between_batches
        )
    else:
        structured_logger.info_operation("process_and_post_v2", "📊 STEP 2: Processing Workflowy content (SEQUENTIAL MODE)...")
        # Keep original sequential processing as fallback
        processing_results = []
        
        async with WorkflowyTesterV2(environment) as tester:
            for i, project in enumerate(projects, 1):
                project_id = project['project_id']
                project_name = project['name']
                
                try:
                    # Set project context for this processing
                    LogContext.set_project_context(project_id, project_name)
                    structured_logger.info_operation("process_and_post_v2", f"🔄 PROCESSING PROJECT {i}/{len(projects)}: {project_name} ({project_id})",
                                                   project_index=i, total_projects=len(projects), project_name=project_name, project_id=project_id)
                    
                    result = await tester.process_single_project(project_id)
                    processing_results.append(result)
                    
                finally:
                    # Clear context after each project (consistent with parallel mode)
                    LogContext.set_project_id(None)
                    LogContext.set_project_name(None)
    
    # Clear project context
    LogContext.set_project_id(None)
    LogContext.set_project_name(None)
    
    # Step 3: Create Tweets/Threads for projects that had new content
    structured_logger.info_operation("process_and_post_v2", "🐦 STEP 3: Creating Tweets/Threads...")
    posting_results = []
    
    # Get list of projects that had content processed
    projects_with_content = []
    for result in processing_results:
        if result['status'] == 'success' and result.get('total_change_tweets', 0) > 0:
            projects_with_content.append(result['project_id'])
    
    # TODO: REMOVE
    structured_logger.info_operation("process_and_post_v2", "TEMPORARY: No projects with content")
    projects_with_content = []
    structured_logger.info_operation("process_and_post_v2", "TEMPORARY: No projects with content")

    structured_logger.info_operation("process_and_post_v2", f"Number of projects with Tweet content: {len(projects_with_content)}", 
                                   projects_with_content_count=len(projects_with_content))
    structured_logger.info_operation("process_and_post_v2", f"Projects with content: {projects_with_content}", 
                                   projects_with_content=projects_with_content)

    if projects_with_content:
        structured_logger.info_operation("process_and_post_v2", f"👥 Projects with new content to post: {projects_with_content}",
                                       projects_to_post=projects_with_content)
        
        # Create TweetPoster V2 and post tweets
        poster = TweetPosterV2(posting_mode="all", environment=environment)
        
        # Process each project individually for better error handling
        for project_id in projects_with_content:
            try:
                LogContext.set_project_id(project_id)
                structured_logger.info_operation("process_and_post_v2", f"🔄 Creating tweets/threads for project {project_id}...", project_id=project_id)

                # Use the project-based posting method
                project_results = await process_single_project_posting_v2(poster, project_id)
                posting_results.append(project_results)
                    
            except Exception as e:
                structured_logger.error_operation("process_and_post_v2", f"❌ Error posting tweets for project {project_id}. Error: {e}", project_id=project_id)
                posting_results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'error': str(e)
                })
    else:
        structured_logger.info_operation("process_and_post_v2", "ℹ️ No projects with new content to post")
        posting_results.append({
            'project_id': 'none',
            'status': 'success',
            'message': 'No new content to post'
        })

    # Clear project context
    LogContext.set_project_id(None)
    
    structured_logger.info_operation("process_and_post_v2", f"📊 Processing results: {processing_results}", processing_results=processing_results)
    structured_logger.info_operation("process_and_post_v2", f"👥 Posting results: {posting_results}", posting_results=posting_results)
    
    return {
        'processing_results': processing_results,
        'posting_results': posting_results
    }


async def process_single_project_posting_v2(poster: TweetPosterV2, project_id: str):
    """Post tweets for a single project using project-based storage."""
    
    # Get project details
    project = poster.storage.get_project_by_id(project_id)
    if not project:
        return {
            'project_id': project_id,
            'status': 'error',
            'error': 'Project not found'
        }
    
    project_name = project['name']
    account_id = project['account_id']
    
    # Load latest tweets from AWS
    all_tweets = poster.get_project_tweet_data(project_id)
    
    if not all_tweets:
        return {
            'project_id': project_id,
            'project_name': project_name,
            'status': 'error',
            'error': 'No tweet data found in AWS'
        }
    
    # Filter only pending tweets
    pending_tweets = [tweet for tweet in all_tweets if tweet.get("status") == "pending"]
    
    if not pending_tweets:
        return {
            'project_id': project_id,
            'project_name': project_name,
            'status': 'success',
            'message': 'No pending tweets to post',
            'total_tweets': len(all_tweets),
            'pending_tweets': 0
        }
    
    structured_logger.info_operation("process_single_project_posting_v2", f"📊 Found {len(pending_tweets)} pending tweets for project {project_id}",
                                   project_id=project_id, pending_count=len(pending_tweets))
    
    # Create aiohttp session for posting
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout, headers=poster.headers) as session:
        
        # Group tweets by thread_id
        from itertools import groupby
        pending_tweets.sort(key=lambda x: x.get("thread_id", ""))
        thread_groups = [list(group) for _, group in groupby(pending_tweets, key=lambda x: x.get("thread_id", ""))]
        
        posted_count = 0
        failed_count = 0
        
        # Process threads (in single mode, only process first thread)
        threads_to_process = thread_groups[:1] if poster.posting_mode == "single" else thread_groups
        
        for thread_tweets in threads_to_process:
            try:
                success = await poster.process_single_thread_for_project(session, thread_tweets, account_id)
                if success:
                    posted_count += len(thread_tweets)
                    structured_logger.info_operation("process_single_project_posting_v2", f"✅ Created thread with {len(thread_tweets)} tweets",
                                                   project_id=project_id, tweet_count=len(thread_tweets))
                else:
                    failed_count += len(thread_tweets)
                    structured_logger.error_operation("process_single_project_posting_v2", f"❌ Failed to create thread with {len(thread_tweets)} tweets.",
                                                    project_id=project_id, tweet_count=len(thread_tweets))
                
                # Delay between threads
                if thread_tweets != threads_to_process[-1]:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                failed_count += len(thread_tweets)
                structured_logger.error_operation("process_single_project_posting_v2", f"❌ Error creating thread with {len(thread_tweets)} tweets. Error: {e}",
                                                project_id=project_id, tweet_count=len(thread_tweets))
        
        # Save updated tweets back to S3
        if posted_count > 0 or failed_count > 0:
            poster.save_updated_tweets_for_project(project_id, all_tweets)
        
        return {
            'project_id': project_id,
            'project_name': project_name,
            'status': 'success' if posted_count > 0 else 'partial' if failed_count > 0 else 'failed',
            'total_tweets': len(all_tweets),
            'pending_tweets': len(pending_tweets),
            'posted_tweets': posted_count,
            'failed_tweets': failed_count,
            'threads_processed': len(threads_to_process),
            'mode': poster.posting_mode
        }


if __name__ == "__main__":
    # Test the updated lambda handler locally
    import sys
    
    # Mock event and context
    event = {
        'environment': 'test'
    }
    
    class MockContext:
        def __init__(self):
            self.function_name = "test-function"
            self.memory_limit_in_mb = 512
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
            self.aws_request_id = "test-request-id"
    
    context = MockContext()
    
    # Run the handler
    result = lambda_handler(event, context)
    
    structured_logger.info_operation("lambda_handler_main", "Lambda handler result:")
    structured_logger.info_operation("lambda_handler_main", json.dumps(result, indent=2, default=str))
