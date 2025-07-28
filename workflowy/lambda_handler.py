# workflowy/lambda_handler.py - Updated to include tweet posting
import json
import asyncio
from test_workflowy import WorkflowyTester
from post_tweets import TweetPoster
import os

# URLs configuration - you can move this to Parameter Store later
WORKFLOWY_URLS = [
    {
        'url': 'https://workflowy.com/s/new-pk-2-reading-cou/bjSyw1MzswiIsciE',
        'name': 'new_pk_2_reading_course'
    },
    # Add more URLs as needed
]

def lambda_handler(event, context):
    """
    Lambda handler for scheduled Workflowy processing AND tweet posting
    """
    print("🚀 Starting Workflowy processing + Tweet posting in Lambda")
    
    # Run the async processing
    results = asyncio.run(process_and_post())
    
    scraping_successful = len([r for r in results['scraping_results'] if r['status'] == 'success'])
    scraping_failed = len([r for r in results['scraping_results'] if r['status'] == 'error'])
    
    posting_successful = len([r for r in results['posting_results'] if r['status'] == 'success'])
    posting_failed = len([r for r in results['posting_results'] if r['status'] == 'error'])
    
    summary = {
        'scraping': {
            'total_processed': len(results['scraping_results']),
            'successful': scraping_successful,
            'failed': scraping_failed,
            'results': results['scraping_results']
        },
        'posting': {
            'total_processed': len(results['posting_results']),
            'successful': posting_successful,
            'failed': posting_failed,
            'results': results['posting_results']
        }
    }
    
    print(f"✅ Scraping complete: {scraping_successful} successful, {scraping_failed} failed")
    print(f"✅ Posting complete: {posting_successful} successful, {posting_failed} failed")
    
    return {
        'statusCode': 200,
        'body': json.dumps(summary, default=str)
    }

async def process_and_post():
    """Process all URLs and then post tweets"""
    
    # Step 1: Scrape Workflowy content
    print("📊 STEP 1: Scraping Workflowy content...")
    scraping_results = []
    
    async with WorkflowyTester() as tester:
        for i, url_config in enumerate(WORKFLOWY_URLS, 1):
            print(f"\n🔄 SCRAPING URL {i}/{len(WORKFLOWY_URLS)}: {url_config['name']}")
            
            result = await tester.process_single_url(
                url_config,
                exclude_node_names=["SpikyPOVs", "Private Notes"]
            )
            scraping_results.append(result)
            
            # Add delay between URLs to be respectful
            if i < len(WORKFLOWY_URLS):
                print(f"⏱️ Waiting 2 seconds before next URL...")
                await asyncio.sleep(2)
    
    # Step 2: Post tweets for users that had new content
    print(f"\n🐦 STEP 2: Posting tweets...")
    posting_results = []
    
    # Get list of users who had content processed
    users_with_content = []
    for result in scraping_results:
        if result['status'] == 'success' and result.get('total_change_tweets', 0) > 0:
            users_with_content.append(result['user_name'])
    
    if users_with_content:
        print(f"👥 Users with new content to post: {users_with_content}")
        
        # Create TweetPoster and post tweets
        poster = TweetPoster(posting_mode="single")  # or "all" if you want to post all threads
        
        # Process each user individually for better error handling
        for user_name in users_with_content:
            try:
                print(f"\n🔄 POSTING tweets for {user_name}...")
                
                # Use the updated run method that can handle individual users
                user_results = await process_single_user_posting(poster, user_name)
                posting_results.append(user_results)
                
                # Add delay between users
                if user_name != users_with_content[-1]:
                    print(f"⏱️ Waiting 10 seconds before next user...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                print(f"❌ Error posting tweets for {user_name}: {e}")
                posting_results.append({
                    'user': user_name,
                    'status': 'error',
                    'error': str(e)
                })
    else:
        print("ℹ️ No users with new content to post")
        posting_results.append({
            'user': 'none',
            'status': 'success',
            'message': 'No new content to post'
        })
    
    return {
        'scraping_results': scraping_results,
        'posting_results': posting_results
    }

async def process_single_user_posting(poster: TweetPoster, user_name: str):
    """Post tweets for a single user using AWS storage"""
    
    # Check if user has account mapping
    account_id = poster.get_account_id(user_name)
    if not account_id:
        return {
            'user': user_name,
            'status': 'error',
            'error': 'No account ID mapping found'
        }
    
    # Load latest tweets from AWS
    all_tweets = poster.load_latest_tweets_from_aws(user_name)
    
    if not all_tweets:
        return {
            'user': user_name,
            'status': 'error',
            'error': 'No tweet data found in AWS'
        }
    
    # Filter only pending tweets
    pending_tweets = [tweet for tweet in all_tweets if tweet.get("status") == "pending"]
    
    if not pending_tweets:
        return {
            'user': user_name,
            'status': 'success',
            'message': 'No pending tweets to post',
            'total_tweets': len(all_tweets),
            'pending_tweets': 0
        }
    
    print(f"📊 Found {len(pending_tweets)} pending tweets for {user_name}")
    
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
                success = await poster.process_single_thread_for_user(session, thread_tweets, account_id)
                if success:
                    posted_count += len(thread_tweets)
                    print(f"✅ Posted thread with {len(thread_tweets)} tweets")
                else:
                    failed_count += len(thread_tweets)
                    print(f"❌ Failed to post thread with {len(thread_tweets)} tweets")
                
                # Delay between threads
                if thread_tweets != threads_to_process[-1]:
                    await asyncio.sleep(5)
                    
            except Exception as e:
                failed_count += len(thread_tweets)
                print(f"❌ Error posting thread: {e}")
        
        return {
            'user': user_name,
            'status': 'success' if posted_count > 0 else 'partial' if failed_count > 0 else 'failed',
            'total_tweets': len(all_tweets),
            'pending_tweets': len(pending_tweets),
            'posted_tweets': posted_count,
            'failed_tweets': failed_count,
            'threads_processed': len(threads_to_process),
            'mode': poster.posting_mode
        }
