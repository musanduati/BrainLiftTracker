"""
Project processing logic for tweet posting
"""

import asyncio
import aiohttp
from typing import Dict, List
from itertools import groupby
from workflowy.storage.project_utils import normalize_project_id
from workflowy.config.logger import logger


class ProjectProcessor:
    """
    Handles project-level processing for tweet posting
    """
    
    def __init__(self, storage_interface, thread_manager, posting_mode: str = "all"):
        """
        Initialize project processor.
        
        Args:
            storage_interface: StorageInterface instance
            thread_manager: ThreadManager instance
            posting_mode: Either "single" or "all" - both now post all threads
        """
        self.storage = storage_interface
        self.thread_manager = thread_manager
        self.posting_mode = posting_mode
    
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
        all_tweets = self.storage.get_project_tweet_data(project_id)
        
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
        pending_tweets.sort(key=lambda x: x.get("thread_id", ""))
        thread_groups = [list(group) for _, group in groupby(pending_tweets, key=lambda x: x.get("thread_id", ""))]
        
        posted_count = 0
        failed_count = 0
        
        # Process threads (in single mode, only process first thread)
        threads_to_process = thread_groups[:1] if self.posting_mode == "single" else thread_groups
        
        for thread_tweets in threads_to_process:
            try:
                success = await self.thread_manager.process_single_thread_for_project(session, thread_tweets, account_id)
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
            self.storage.save_updated_tweets_for_project(project_id, all_tweets)
        
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
    
    async def process_multiple_projects(self, session: aiohttp.ClientSession, project_ids: List[str]) -> List[Dict]:
        """
        Process multiple projects.
        
        Args:
            session: aiohttp session
            project_ids: List of project identifiers
            
        Returns:
            List of processing results
        """
        results = []
        for project_id in project_ids:
            try:
                result = await self.process_project(session, project_id)
                results.append(result)
                
                # Delay between projects
                if project_id != project_ids[-1]:
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"❌ Error processing project {project_id}: {e}")
                results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def get_active_projects_with_tweets(self) -> List[str]:
        """
        Get list of active projects that have tweet data.
        
        Returns:
            List of project IDs
        """
        projects = self.storage.get_all_projects()
        active_projects = []
        
        for project in projects:
            if project.get('active', False):
                project_id = project['project_id']
                tweets = self.storage.get_project_tweet_data(project_id)
                if tweets:
                    active_projects.append(project_id)
        
        return active_projects
