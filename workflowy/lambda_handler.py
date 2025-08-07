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
from workflowy.config.logger import logger


def lambda_handler(event, context):
    """
    Lambda handler V2 for:
    1. Bulk URL processing (when event contains brainlift URLs)
    2. Scheduled project processing AND tweet posting (default behavior)
    """
    
    # Determine environment from event or context
    environment = os.getenv('ENVIRONMENT', 'test')
    
    # Check if this is a bulk URL processing request
    if is_bulk_url_request_v2(event):
        logger.info("🔗 Processing bulk URL upload request (V2)")
        return handle_bulk_url_processing_v2(event, environment)
    else:
        logger.info(f"🚀 Starting project-based processing + Tweet posting in Lambda (Environment: {environment})")
        
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
        
        logger.info(f"✅ Processing complete: {scraping_successful} successful, {scraping_failed} failed")
        logger.info(f"✅ Posting complete: {posting_successful} successful, {posting_failed} failed")
        
        return {
            'statusCode': 200,
            'body': json.dumps(summary, default=str)
        }


async def process_and_post_v2(environment: str = 'test'):
    """Process all projects and then post tweets (project-based approach)."""
    
    # Step 1: Get active projects from DynamoDB
    logger.info("📊 STEP 1: Loading active projects from DynamoDB...")
    storage = AWSStorageV2(environment)
    projects = storage.get_all_projects()
    
    if not projects:
        logger.error("❌ No active projects found in DynamoDB!")
        return {
            'processing_results': [{
                'status': 'error',
                'error': 'No active projects configured in DynamoDB'
            }],
            'posting_results': []
        }
    
    logger.info(f"📋 Found {len(projects)} active project(s) to process")
    for project in projects:
        logger.info(f"  • {project['name']} ({project['project_id']}): {project['url']}")
    
    # Step 2: Process Workflowy content for all projects
    logger.info("📊 STEP 2: Processing Workflowy content...")
    processing_results = []
    
    async with WorkflowyTesterV2(environment) as tester:
        for i, project in enumerate(projects, 1):
            project_id = project['project_id']
            project_name = project['name']
            
            logger.info(f"🔄 PROCESSING PROJECT {i}/{len(projects)}: {project_name} ({project_id})")
            
            result = await tester.process_single_project(project_id)
            processing_results.append(result)
    
    # Step 3: Post tweets for projects that had new content
    logger.info(f"🐦 STEP 3: Posting tweets...")
    posting_results = []
    
    # Get list of projects that had content processed
    projects_with_content = []
    for result in processing_results:
        if result['status'] == 'success' and result.get('total_change_tweets', 0) > 0:
            projects_with_content.append(result['project_id'])

    if projects_with_content:
        logger.info(f"👥 Projects with new content to post: {projects_with_content}")
        
        # Create TweetPoster V2 and post tweets
        poster = TweetPosterV2(posting_mode="all", environment=environment)
        
        # Process each project individually for better error handling
        for project_id in projects_with_content:
            try:
                logger.info(f"🔄 POSTING tweets for project {project_id}...")

                # Use the project-based posting method
                project_results = await process_single_project_posting_v2(poster, project_id)
                posting_results.append(project_results)
                
                # Add delay between projects
                if project_id != projects_with_content[-1]:
                    logger.info(f"⏱️ Waiting 3 seconds before next project...")
                    await asyncio.sleep(3)
                    
            except Exception as e:
                logger.error(f"❌ Error posting tweets for project {project_id}: {e}")
                posting_results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'error': str(e)
                })
    else:
        logger.info("ℹ️ No projects with new content to post")
        posting_results.append({
            'project_id': 'none',
            'status': 'success',
            'message': 'No new content to post'
        })

    logger.info(f"📊 Processing results: {processing_results}")
    logger.info(f"👥 Posting results: {posting_results}")
    
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
    
    logger.info(f"📊 Found {len(pending_tweets)} pending tweets for project {project_id}")
    
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
                    logger.info(f"✅ Posted thread with {len(thread_tweets)} tweets")
                else:
                    failed_count += len(thread_tweets)
                    logger.error(f"❌ Failed to post thread with {len(thread_tweets)} tweets")
                
                # Delay between threads
                if thread_tweets != threads_to_process[-1]:
                    await asyncio.sleep(5)
                    
            except Exception as e:
                failed_count += len(thread_tweets)
                logger.error(f"❌ Error posting thread: {e}")
        
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
    
    print("Lambda handler result:")
    print(json.dumps(result, indent=2, default=str))
