"""
Main TweetPosterV2 class - orchestrates all tweet posting operations
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from workflowy.config.logger import logger
from workflowy.storage.project_utils import normalize_project_id

# Import from poster submodules
from .storage_interface import StorageInterface
from .twitter_api import TwitterAPIClient
from .thread_manager import ThreadManager
from .project_processor import ProjectProcessor


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
        if posting_mode not in ["single", "all"]:
            raise ValueError("posting_mode must be either 'single' or 'all'")
        
        self.posting_mode = posting_mode
        self.environment = environment
        
        # Initialize components
        self.storage_interface = StorageInterface(environment)
        self.twitter_api = TwitterAPIClient()
        self.thread_manager = ThreadManager(self.twitter_api)
        self.project_processor = ProjectProcessor(
            self.storage_interface, 
            self.thread_manager, 
            posting_mode
        )
        
        # For backward compatibility
        self.storage = self.storage_interface.storage
        self.api_base = self.twitter_api.api_base
        self.api_key = self.twitter_api.api_key
        self.headers = self.twitter_api.headers
        
        logger.info(f"🔄 TweetPoster V2 initialized (Mode: {posting_mode}, Environment: {environment})")
    
    # Delegate storage methods for backward compatibility
    def get_account_id_for_project(self, project_id: str) -> Optional[str]:
        """Get account ID for a project."""
        return self.storage_interface.get_account_id_for_project(project_id)
    
    def get_project_tweet_data(self, project_id: str) -> List[Dict]:
        """Load latest tweets for a project from S3."""
        return self.storage_interface.get_project_tweet_data(project_id)
    
    def save_updated_tweets_for_project(self, project_id: str, tweets: List[Dict]):
        """Save updated tweet data back to S3 after posting."""
        self.storage_interface.save_updated_tweets_for_project(project_id, tweets)
    
    # Delegate Twitter API methods for backward compatibility
    async def create_tweet(self, session: aiohttp.ClientSession, text: str, account_id: str) -> Optional[int]:
        """Create a tweet using the API."""
        return await self.twitter_api.create_tweet(session, text, account_id)
    
    async def post_tweet(self, session: aiohttp.ClientSession, tweet_id: int) -> bool:
        """Post a created tweet."""
        return await self.twitter_api.post_tweet(session, tweet_id)
    
    async def create_thread(self, session: aiohttp.ClientSession, thread_tweets: List[Dict], account_id: str) -> Optional[str]:
        """Create a thread of tweets."""
        return await self.twitter_api.create_thread(session, thread_tweets, account_id)
    
    async def post_thread(self, session: aiohttp.ClientSession, thread_id: str) -> bool:
        """Post a created thread."""
        return await self.twitter_api.post_thread(session, thread_id)
    
    # Delegate thread management methods for backward compatibility
    def is_thread(self, thread_tweets: List[Dict]) -> bool:
        """Check if tweets constitute a thread."""
        return self.thread_manager.is_thread(thread_tweets)
    
    def group_tweets_by_thread(self, tweets: List[Dict]) -> Dict[str, List[Dict]]:
        """Group tweets by thread_id."""
        return self.thread_manager.group_tweets_by_thread(tweets)
    
    async def process_single_tweet(self, session: aiohttp.ClientSession, tweet_data: Dict, account_id: str) -> bool:
        """Process a single tweet."""
        return await self.thread_manager.process_single_tweet(session, tweet_data, account_id)
    
    async def process_single_thread_for_project(self, session: aiohttp.ClientSession, 
                                               thread_tweets: List[Dict], 
                                               account_id: str) -> bool:
        """Process a single thread for a project."""
        return await self.thread_manager.process_single_thread_for_project(session, thread_tweets, account_id)
    
    # Delegate project processing for backward compatibility
    async def process_project(self, session: aiohttp.ClientSession, project_id: str) -> Dict:
        """Process tweets for a specific project."""
        return await self.project_processor.process_project(session, project_id)
    
    async def run(self, target_project_ids: Optional[List[str]] = None, posting_mode: str = None):
        """
        Run tweet posting for specified projects or all projects.
        
        Args:
            target_project_ids: List of project IDs to process (None = all projects)
            posting_mode: Override posting mode
        """
        if posting_mode:
            self.posting_mode = posting_mode
            self.project_processor.posting_mode = posting_mode
        
        logger.info(f"🚀 Starting TweetPoster V2 (Mode: {self.posting_mode})")
        
        # Get projects to process
        if target_project_ids:
            projects = []
            for project_id in target_project_ids:
                project = self.storage_interface.get_project_by_id(project_id)
                if project:
                    projects.append(project)
                else:
                    logger.warning(f"⚠️ Project not found: {project_id}")
        else:
            projects = self.storage_interface.get_all_projects()
        
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


# Standalone functions for backward compatibility
def preview_what_will_be_posted_v2(target_project_ids: Optional[List[str]] = None, posting_mode: str = "all"):
    """
    Preview what tweets will be posted without actually posting them.
    """
    logger.info("📋 PREVIEW MODE - No tweets will actually be posted")
    logger.info("="*60)
    
    poster = TweetPosterV2(posting_mode)
    
    # Get projects to preview
    if target_project_ids:
        projects = []
        for project_id in target_project_ids:
            project = poster.storage_interface.get_project_by_id(project_id)
            if project:
                projects.append(project)
    else:
        projects = poster.storage_interface.get_all_projects()
    
    if not projects:
        logger.info("No projects found")
        return
    
    total_pending = 0
    
    for project in projects:
        project_id = project['project_id']
        project_name = project['name']
        account_id = project['account_id']
        
        tweets = poster.get_project_tweet_data(project_id)
        
        if not tweets:
            continue
        
        pending_tweets = [t for t in tweets if t.get("status") == "pending"]
        
        if not pending_tweets:
            continue
        
        logger.info(f"\n🏷️ Project: {project_name} ({project_id})")
        logger.info(f"   Account ID: {account_id}")
        logger.info(f"   Pending Tweets: {len(pending_tweets)}")
        
        # Group by thread
        threads = poster.group_tweets_by_thread(pending_tweets)
        
        for thread_id, thread_tweets in threads.items():
            if poster.is_thread(thread_tweets):
                logger.info(f"\n   🧵 Thread: {thread_id} ({len(thread_tweets)} tweets)")
                for i, tweet in enumerate(thread_tweets, 1):
                    text = tweet.get('content_formatted', tweet.get('text', ''))
                    logger.info(f"      Tweet {i}: {text[:100]}...")
            else:
                tweet = thread_tweets[0]
                text = tweet.get('content_formatted', tweet.get('text', ''))
                logger.info(f"   📝 Single: {text[:100]}...")
        
        total_pending += len(pending_tweets)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 Total pending tweets across all projects: {total_pending}")


async def main():
    """Main entry point for testing."""
    poster = TweetPosterV2(posting_mode="all", environment="test")
    await poster.run()


if __name__ == "__main__":
    asyncio.run(main())
