"""
TweetPoster V2 - Project-based Tweet Posting
Updated to use project-based identification instead of user-based identification.
Eliminates dependency on user_name for account mapping and content loading.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
from aws_storage_v2 import AWSStorageV2
from project_id_utils import normalize_project_id
from logger_config import logger


class TweetPosterV2:
    """
    Updated TweetPoster using project-based identification.
    Posts tweets for projects instead of users.
    """
    
    def __init__(self, posting_mode: str = "all", environment: str = 'test'):
        """
        Initialize TweetPoster V2.
        
        Args:
            posting_mode: Either "single" or "all" - both now post all threads
            environment: Environment to use (test/prod)
        """
        self.api_base = "http://98.86.153.32/api/v1"
        self.api_key = "6b6fea7c92a74e005a3c59a0834948c7cab4f50be333a68e852f09314120243d"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.posting_mode = posting_mode
        self.environment = environment
        
        # Use project-based storage
        self.storage = AWSStorageV2(environment)
        
        if posting_mode not in ["single", "all"]:
            raise ValueError("posting_mode must be either 'single' or 'all'")
        
        logger.info(f"🔄 TweetPoster V2 initialized (Mode: {posting_mode}, Environment: {environment})")
    
    def get_account_id_for_project(self, project_id: str) -> Optional[str]:
        """
        Get account ID for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            str: Account ID or None if not found
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"❌ Invalid project_id format: {project_id}")
            return None
        
        account_id = self.storage.get_account_id_for_project(project_id)
        if not account_id:
            logger.error(f"❌ No account mapping found for project: {project_id}")
        
        return account_id
    
    def get_project_tweet_data(self, project_id: str) -> List[Dict]:
        """
        Load latest tweets for a project from S3.
        
        Args:
            project_id: Project identifier
            
        Returns:
            list: Tweet data for the project
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"❌ Invalid project_id format: {project_id}")
            return []
        
        return self.storage.load_latest_tweets_from_s3(project_id)
    
    def save_updated_tweets_for_project(self, project_id: str, tweets: List[Dict]):
        """
        Save updated tweet data back to S3 after posting.
        
        Args:
            project_id: Project identifier
            tweets: Updated tweet data
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"❌ Invalid project_id format: {project_id}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Save with updated status
            updated_url = self.storage.save_change_tweets(project_id, tweets, f"{timestamp}_updated")
            logger.info(f"📄 Updated tweet statuses saved to S3: {updated_url}")
            
        except Exception as e:
            logger.error(f"❌ Error saving updated tweets for project {project_id}: {e}")
    
    async def create_tweet(self, session: aiohttp.ClientSession, text: str, account_id: str) -> Optional[int]:
        """
        Create a tweet using the API.
        
        Args:
            session: aiohttp session
            text: Tweet text
            account_id: Account ID
            
        Returns:
            int: Tweet ID if successful, None otherwise
        """
        try:
            payload = {
                "text": text,
                "account_id": int(account_id)
            }
            
            async with session.post(f"{self.api_base}/tweet", json=payload) as response:
                if response.status == 201:
                    data = await response.json()
                    tweet_id = data.get('tweet_id')
                    logger.debug(f"✅ Tweet created with ID: {tweet_id}")
                    return tweet_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to create tweet: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error creating tweet: {e}")
            return None
    
    async def post_tweet(self, session: aiohttp.ClientSession, tweet_id: int) -> bool:
        """
        Post a created tweet.
        
        Args:
            session: aiohttp session
            tweet_id: Tweet ID to post
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = {"tweet_id": tweet_id}
            
            async with session.post(f"{self.api_base}/tweet/post/{tweet_id}", json=payload) as response:
                if response.status == 200:
                    logger.debug(f"✅ Tweet {tweet_id} posted successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to post tweet {tweet_id}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error posting tweet {tweet_id}: {e}")
            return False
    
    async def create_thread(self, session: aiohttp.ClientSession, thread_tweets: List[Dict], account_id: str) -> Optional[str]:
        """
        Create a thread of tweets.
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweet dictionaries
            account_id: Account ID
            
        Returns:
            str: Thread ID if successful, None otherwise
        """
        try:
            tweet_texts = []
            for tweet in thread_tweets:
                if isinstance(tweet, dict):
                    if 'content' in tweet and isinstance(tweet['content'], dict):
                        # New format: nested content
                        text = tweet['content'].get('text', '')
                    else:
                        # Support both old and current formats
                        text = tweet.get('text', '') or tweet.get('content_formatted', '')
                else:
                    text = str(tweet)
                
                if text:
                    tweet_texts.append(text)
            
            if not tweet_texts:
                logger.error("❌ No valid tweet texts found in thread")
                return None
            
            payload = {
                "tweets": tweet_texts,
                "account_id": int(account_id)
            }
            
            async with session.post(f"{self.api_base}/thread", json=payload) as response:
                if response.status == 201:
                    data = await response.json()
                    thread_id = data.get('thread_id')
                    logger.debug(f"✅ Thread created with ID: {thread_id}")
                    return thread_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to create thread: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error creating thread: {e}")
            return None
    
    async def post_thread(self, session: aiohttp.ClientSession, thread_id: str) -> bool:
        """
        Post a created thread.
        
        Args:
            session: aiohttp session
            thread_id: Thread ID to post
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = {"thread_id": thread_id}
            
            async with session.post(f"{self.api_base}/thread/post/{thread_id}", json=payload) as response:
                if response.status == 200:
                    logger.debug(f"✅ Thread {thread_id} posted successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to post thread {thread_id}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error posting thread {thread_id}: {e}")
            return False
    
    def is_thread(self, thread_tweets: List[Dict]) -> bool:
        """Check if tweets constitute a thread (more than one tweet)."""
        return len(thread_tweets) > 1
    
    def group_tweets_by_thread(self, tweets: List[Dict]) -> Dict[str, List[Dict]]:
        """Group tweets by thread_id."""
        threads = {}
        
        for tweet in tweets:
            thread_id = tweet.get("thread_id", "single")
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(tweet)
        
        return threads
    
    async def process_single_tweet(self, session: aiohttp.ClientSession, tweet_data: Dict, account_id: str) -> bool:
        """
        Process a single tweet.
        
        Args:
            session: aiohttp session
            tweet_data: Tweet data dictionary
            account_id: Account ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract text based on format
            if 'content' in tweet_data and isinstance(tweet_data['content'], dict):
                # New format: nested content
                text = tweet_data['content'].get('text', '')
            else:
                # Support both old and current formats
                text = tweet_data.get('text', '') or tweet_data.get('content_formatted', '')
            
            if not text:
                logger.warning("⚠️ Empty tweet text, skipping")
                tweet_data["status"] = "skipped"
                tweet_data["error"] = "Empty text"
                return False
            
            logger.info(f"📝 Creating tweet: {text[:50]}...")
            
            # Create tweet
            tweet_id = await self.create_tweet(session, text, account_id)
            if not tweet_id:
                tweet_data["status"] = "failed"
                tweet_data["error"] = "Failed to create tweet"
                return False
            
            tweet_data["tweet_id"] = tweet_id
            tweet_data["status"] = "created"
            
            # Post tweet
            success = await self.post_tweet(session, tweet_id)
            
            if success:
                tweet_data["status"] = "posted"
                tweet_data["posted_at"] = datetime.now().isoformat()
                logger.info(f"   ✅ Tweet posted successfully")
            else:
                tweet_data["status"] = "created_not_posted"
                logger.warning(f"   ⚠️ Tweet created but posting failed")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error processing single tweet: {e}")
            tweet_data["status"] = "failed"
            tweet_data["error"] = str(e)
            return False
    
    async def process_single_thread_for_project(self, session: aiohttp.ClientSession, 
                                               thread_tweets: List[Dict], 
                                               account_id: str) -> bool:
        """
        Process a single thread for a project.
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweets in the thread
            account_id: Account ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not thread_tweets:
            logger.warning("⚠️ Empty thread, skipping")
            return False
        
        try:
            if self.is_thread(thread_tweets):
                logger.info(f"🧵 Processing thread with {len(thread_tweets)} tweets")
                
                # Create thread
                thread_id = await self.create_thread(session, thread_tweets, account_id)
                if not thread_id:
                    for tweet in thread_tweets:
                        tweet["status"] = "failed"
                        tweet["error"] = "Failed to create thread"
                    return False
                
                # Update all tweets with thread info
                for tweet in thread_tweets:
                    tweet["thread_id"] = thread_id
                    tweet["status"] = "created"
                
                # Post thread
                success = await self.post_thread(session, thread_id)
                
                # Update status for all tweets
                for tweet in thread_tweets:
                    if success:
                        tweet["status"] = "posted"
                        tweet["posted_at"] = datetime.now().isoformat()
                    else:
                        tweet["status"] = "created_not_posted"
                
                if success:
                    logger.info(f"   ✅ Thread with {len(thread_tweets)} tweets posted successfully")
                else:
                    logger.warning(f"   ⚠️ Thread created but posting failed")
                
                return success
            else:
                # Single tweet
                return await self.process_single_tweet(session, thread_tweets[0], account_id)
                
        except Exception as e:
            logger.error(f"❌ Error processing thread: {e}")
            for tweet in thread_tweets:
                tweet["status"] = "failed"
                tweet["error"] = str(e)
            return False
    
    async def process_project(self, session: aiohttp.ClientSession, project_id: str) -> Dict:
        """
        Process tweets for a specific project.
        
        Args:
            session: aiohttp session
            project_id: Project identifier
            
        Returns:
            dict: Processing results
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            error_msg = f"Invalid project_id format: {project_id}"
            logger.error(f"❌ {error_msg}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': error_msg
            }
        
        logger.info(f"{'='*50}")
        logger.info(f"PROCESSING PROJECT: {project_id}")
        logger.info(f"{'='*50}")
        
        # Get project details
        project = self.storage.get_project_by_id(project_id)
        if not project:
            error_msg = f"Project not found: {project_id}"
            logger.error(f"❌ {error_msg}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': error_msg
            }
        
        project_name = project['name']
        account_id = project['account_id']
        
        logger.info(f"🏷️ Project Name: {project_name}")
        logger.info(f"🎯 Account ID: {account_id}")
        
        # Load tweet data
        all_tweets = self.get_project_tweet_data(project_id)
        
        if not all_tweets:
            logger.warning(f"⚠️ No tweet data found for project: {project_id}")
            return {
                'project_id': project_id,
                'project_name': project_name,
                'status': 'success',
                'message': 'No tweet data found',
                'total_tweets': 0,
                'pending_tweets': 0,
                'posted_tweets': 0,
                'failed_tweets': 0
            }
        
        logger.info(f"📄 Loaded {len(all_tweets)} tweets for project {project_id}")
        
        # Filter only pending tweets
        pending_tweets = [tweet for tweet in all_tweets if tweet.get("status") == "pending"]
        
        if not pending_tweets:
            logger.info(f"ℹ️ No pending tweets to post for project {project_id}")
            return {
                'project_id': project_id,
                'project_name': project_name,
                'status': 'success',
                'message': 'No pending tweets to post',
                'total_tweets': len(all_tweets),
                'pending_tweets': 0,
                'posted_tweets': 0,
                'failed_tweets': 0
            }
        
        logger.info(f"📊 Found {len(pending_tweets)} pending tweets to post")
        
        # Group tweets by thread
        from itertools import groupby
        pending_tweets.sort(key=lambda x: x.get("thread_id", ""))
        thread_groups = [list(group) for _, group in groupby(pending_tweets, key=lambda x: x.get("thread_id", ""))]
        
        posted_count = 0
        failed_count = 0
        
        # Process threads (in single mode, only process first thread)
        threads_to_process = thread_groups[:1] if self.posting_mode == "single" else thread_groups
        
        for thread_tweets in threads_to_process:
            try:
                success = await self.process_single_thread_for_project(session, thread_tweets, account_id)
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
            self.save_updated_tweets_for_project(project_id, all_tweets)
        
        status = 'success' if posted_count > 0 else 'partial' if failed_count > 0 else 'failed'
        
        return {
            'project_id': project_id,
            'project_name': project_name,
            'status': status,
            'total_tweets': len(all_tweets),
            'pending_tweets': len(pending_tweets),
            'posted_tweets': posted_count,
            'failed_tweets': failed_count,
            'threads_processed': len(threads_to_process),
            'mode': self.posting_mode
        }
    
    async def run(self, target_project_ids: Optional[List[str]] = None, posting_mode: str = None):
        """
        Run tweet posting for specified projects or all projects.
        
        Args:
            target_project_ids: List of project IDs to process (None = all projects)
            posting_mode: Override posting mode
        """
        if posting_mode:
            self.posting_mode = posting_mode
        
        logger.info(f"🚀 Starting TweetPoster V2 (Mode: {self.posting_mode})")
        
        # Get projects to process
        if target_project_ids:
            projects = []
            for project_id in target_project_ids:
                project = self.storage.get_project_by_id(project_id)
                if project:
                    projects.append(project)
                else:
                    logger.warning(f"⚠️ Project not found: {project_id}")
        else:
            projects = self.storage.get_all_projects()
        
        if not projects:
            logger.warning("⚠️ No projects found to process")
            return
        
        logger.info(f"📋 Processing {len(projects)} project(s)")
        
        # Create aiohttp session
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=self.headers) as session:
            
            results = []
            total_posted = 0
            total_failed = 0
            
            for i, project in enumerate(projects, 1):
                project_id = project['project_id']
                project_name = project['name']
                
                logger.info(f"🔄 PROCESSING PROJECT {i}/{len(projects)}: {project_name} ({project_id})")
                
                try:
                    result = await self.process_project(session, project_id)
                    results.append(result)
                    
                    posted = result.get('posted_tweets', 0)
                    failed = result.get('failed_tweets', 0)
                    total_posted += posted
                    total_failed += failed
                    
                    if posted > 0:
                        logger.info(f"✅ Project {project_name}: {posted} tweets posted")
                    elif failed > 0:
                        logger.warning(f"⚠️ Project {project_name}: {failed} tweets failed")
                    else:
                        logger.info(f"ℹ️ Project {project_name}: No tweets to post")
                    
                    # Delay between projects
                    if i < len(projects):
                        logger.info(f"⏱️ Waiting 10 seconds before next project...")
                        await asyncio.sleep(10)
                        
                except Exception as e:
                    error_result = {
                        'project_id': project_id,
                        'project_name': project_name,
                        'status': 'error',
                        'error': str(e)
                    }
                    results.append(error_result)
                    logger.error(f"❌ Error processing project {project_name}: {e}")
        
        # Summary
        logger.info(f"{'='*60}")
        logger.info(f"🏁 TWEET POSTING COMPLETE")
        logger.info(f"📊 Projects processed: {len(projects)}")
        logger.info(f"✅ Total tweets posted: {total_posted}")
        logger.info(f"❌ Total tweets failed: {total_failed}")
        logger.info(f"{'='*60}")
        
        # Detailed results
        for result in results:
            status = result['status']
            project_id = result['project_id']
            project_name = result.get('project_name', 'Unknown')
            
            if status == 'success':
                posted = result.get('posted_tweets', 0)
                if posted > 0:
                    logger.info(f"  ✅ {project_name} ({project_id}): {posted} tweets posted")
                else:
                    logger.info(f"  ℹ️ {project_name} ({project_id}): No tweets to post")
            else:
                error = result.get('error', 'Unknown error')
                logger.info(f"  ❌ {project_name} ({project_id}): {error}")


def preview_what_will_be_posted_v2(target_project_ids: Optional[List[str]] = None, posting_mode: str = "all"):
    """
    Preview what tweets will be posted for projects.
    
    Args:
        target_project_ids: List of project IDs to preview (None = all projects)
        posting_mode: Posting mode to use
    """
    logger.info(f"👁️ PREVIEW MODE - What will be posted (Mode: {posting_mode})")
    
    storage = AWSStorageV2('test')
    
    # Get projects to preview
    if target_project_ids:
        projects = []
        for project_id in target_project_ids:
            project = storage.get_project_by_id(project_id)
            if project:
                projects.append(project)
            else:
                logger.warning(f"⚠️ Project not found: {project_id}")
    else:
        projects = storage.get_all_projects()
    
    if not projects:
        logger.warning("⚠️ No projects found")
        return
    
    total_pending = 0
    total_threads = 0
    
    for project in projects:
        project_id = project['project_id']
        project_name = project['name']
        account_id = project['account_id']
        
        logger.info(f"\n{'='*50}")
        logger.info(f"PROJECT: {project_name} ({project_id})")
        logger.info(f"ACCOUNT: {account_id}")
        logger.info(f"{'='*50}")
        
        # Load tweet data
        all_tweets = storage.load_latest_tweets_from_s3(project_id)
        
        if not all_tweets:
            logger.info("ℹ️ No tweet data found")
            continue
        
        # Filter pending tweets
        pending_tweets = [tweet for tweet in all_tweets if tweet.get("status") == "pending"]
        
        if not pending_tweets:
            logger.info("ℹ️ No pending tweets to post")
            continue
        
        # Group by threads
        from itertools import groupby
        pending_tweets.sort(key=lambda x: x.get("thread_id", ""))
        thread_groups = [list(group) for _, group in groupby(pending_tweets, key=lambda x: x.get("thread_id", ""))]
        
        threads_to_show = thread_groups[:1] if posting_mode == "single" else thread_groups
        
        logger.info(f"📊 {len(pending_tweets)} pending tweets in {len(threads_to_show)} thread(s)")
        total_pending += len(pending_tweets)
        total_threads += len(threads_to_show)
        
        for i, thread_tweets in enumerate(threads_to_show, 1):
            thread_id = thread_tweets[0].get("thread_id", "single")
            section = thread_tweets[0].get("section", "unknown")
            
            if len(thread_tweets) > 1:
                logger.info(f"\n🧵 THREAD {i}: {thread_id} ({section}) - {len(thread_tweets)} tweets")
            else:
                logger.info(f"\n📝 SINGLE TWEET {i}: {section}")
            
            for j, tweet in enumerate(thread_tweets, 1):
                # Extract text based on format
                if 'content' in tweet and isinstance(tweet['content'], dict):
                    text = tweet['content'].get('text', '')
                else:
                    text = tweet.get('text', '')
                
                preview_text = text[:100] + "..." if len(text) > 100 else text
                logger.info(f"   {j}. {preview_text}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"👁️ PREVIEW SUMMARY")
    logger.info(f"📊 Projects with pending tweets: {len([p for p in projects if storage.load_latest_tweets_from_s3(p['project_id'])])}")
    logger.info(f"📝 Total pending tweets: {total_pending}")
    logger.info(f"🧵 Total threads: {total_threads}")
    logger.info(f"{'='*60}")


async def main():
    """Main function for CLI usage."""
    import sys
    
    args = sys.argv[1:]
    
    if args and args[0] == "preview":
        # Preview mode
        target_project_ids = args[1:] if len(args) > 1 else None
        preview_what_will_be_posted_v2(target_project_ids)
        return
    
    # Normal posting mode
    posting_mode = "all"  # Default mode
    target_project_ids = args if args else None
    
    poster = TweetPosterV2(posting_mode=posting_mode, environment='test')
    await poster.run(target_project_ids)


if __name__ == "__main__":
    logger.info("TweetPoster V2 - Project-based Tweet Posting")
    logger.info("Usage:")
    logger.info("  python post_tweets_v2.py [project_id1] [project_id2]        # Post for specific projects")
    logger.info("  python post_tweets_v2.py                                    # Post for all projects")
    logger.info("  python post_tweets_v2.py preview [project_id1]              # Preview what will be posted")
    
    asyncio.run(main())
