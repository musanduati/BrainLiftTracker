"""
Thread management logic for tweet posting
"""

import aiohttp
from typing import List, Dict
from datetime import datetime
from workflowy.config.logger import logger


class ThreadManager:
    """
    Handles thread-related operations for tweet posting
    """
    
    def __init__(self, twitter_api):
        """
        Initialize thread manager.
        
        Args:
            twitter_api: TwitterAPIClient instance
        """
        self.twitter_api = twitter_api
    
    def is_thread(self, thread_tweets: List[Dict]) -> bool:
        """Check if tweets constitute a thread (more than one tweet)."""
        return len(thread_tweets) > 1
    
    def group_tweets_by_thread(self, tweets: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group tweets by thread_id.
        
        Args:
            tweets: List of tweet dictionaries
            
        Returns:
            Dict with thread_id as key and list of tweets as value
        """
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
            tweet_id = await self.twitter_api.create_tweet(session, text, account_id)
            if not tweet_id:
                tweet_data["status"] = "failed"
                tweet_data["error"] = "Failed to create tweet"
                return False
            
            tweet_data["tweet_id"] = tweet_id
            tweet_data["status"] = "created"
            
            # Post tweet
            success = await self.twitter_api.post_tweet(session, tweet_id)
            
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
                thread_id = await self.twitter_api.create_thread(session, thread_tweets, account_id)
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
                success = await self.twitter_api.post_thread(session, thread_id)
                
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
