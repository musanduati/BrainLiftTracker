"""
Twitter API client for tweet posting
"""

import aiohttp
from typing import List, Dict, Optional
from workflowy.config.logger import logger
from workflowy.core.scraper.tweet_generation import convert_markdown_urls_to_plain


class TwitterAPIClient:
    """
    Handles all Twitter API interactions
    """
    
    def __init__(self):
        """Initialize Twitter API client."""
        self.api_base = "http://98.86.153.32/api/v1"
        self.api_key = "6b6fea7c92a74e005a3c59a0834948c7cab4f50be333a68e852f09314120243d"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
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
            # Convert markdown URLs to plain URLs before sending to Twitter
            processed_text = convert_markdown_urls_to_plain(text)
            
            payload = {
                "text": processed_text,
                "account_id": int(account_id)
            }
            
            async with session.post(f"{self.api_base}/tweet", json=payload, headers=self.headers) as response:
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
            
            async with session.post(f"{self.api_base}/tweet/post/{tweet_id}", json=payload, headers=self.headers) as response:
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
                    # Convert markdown URLs to plain URLs before adding to payload
                    processed_text = convert_markdown_urls_to_plain(text)
                    tweet_texts.append(processed_text)
            
            if not tweet_texts:
                logger.error("❌ No valid tweet texts found in thread")
                return None
            
            payload = {
                "tweets": tweet_texts,
                "account_id": int(account_id)
            }
            
            async with session.post(f"{self.api_base}/thread", json=payload, headers=self.headers) as response:
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
            
            async with session.post(f"{self.api_base}/thread/post/{thread_id}", json=payload, headers=self.headers) as response:
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
