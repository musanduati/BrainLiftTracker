import json
import asyncio
import aiohttp
from typing import List, Dict, Optional
from pathlib import Path
import logging
import re
from datetime import datetime

from aws_storage import AWSStorage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User to Account ID mapping
USER_ACCOUNT_MAPPING = {
    # "sanket_ghia": 2,
    # "musa_nduati": 3,
    # "yuki_tanaka": 3,
    # "elijah_johnson": 5,
    # Add more users as needed
    # "agentic_frameworks": 2,
    # "new_pk_2_reading_course": 2,
    "new_pk_2_reading_course": 3,
}

class TweetPoster:
    def __init__(self, posting_mode: str = "single"):
        """
        Initialize TweetPoster.
        
        Args:
            posting_mode: Either "single" (post only top priority thread) or "all" (post all threads)
        """
        # self.api_base = "http://localhost:5555/api/v1"
        # self.api_key = "2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb"
        self.api_base = "http://98.86.153.32/api/v1"
        self.api_key = "6b6fea7c92a74e005a3c59a0834948c7cab4f50be333a68e852f09314120243d"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.users_dir = Path("users")
        self.posting_mode = posting_mode
        
        # Add AWS storage for loading tweet data
        self.storage = AWSStorage()
        
        # Validate posting mode
        if posting_mode not in ["single", "all"]:
            raise ValueError("posting_mode must be either 'single' or 'all'")

    def get_account_id(self, user_name: str) -> Optional[int]:
        """Get account ID for a user."""
        return USER_ACCOUNT_MAPPING.get(user_name)

    def get_available_users(self) -> List[str]:
        """Get list of available users from the users directory."""
        if not self.users_dir.exists():
            return []
        
        users = []
        for user_dir in self.users_dir.iterdir():
            if user_dir.is_dir() and user_dir.name in USER_ACCOUNT_MAPPING:
                users.append(user_dir.name)
        
        return sorted(users)

    def find_latest_tweet_file(self, user_name: str) -> Optional[Path]:
        """
        Find the latest timestamped change_tweets file for a user.
        
        Args:
            user_name: Name of the user
            
        Returns:
            Path to the latest change_tweets file or None if not found
        """
        user_dir = self.users_dir / user_name
        
        if not user_dir.exists():
            logger.error(f"❌ User directory not found: {user_dir}")
            return None
        
        # Look for change_tweets files with timestamp pattern
        pattern = f"{user_name}_change_tweets_*.json"
        tweet_files = list(user_dir.glob(pattern))
        
        if not tweet_files:
            logger.warning(f"⚠️ No change_tweets files found for {user_name}")
            return None
        
        # Sort by timestamp (filename contains YYYYMMDD-HHMMSS)
        tweet_files.sort(key=lambda x: x.name, reverse=True)
        latest_file = tweet_files[0]
        
        logger.info(f"📄 Found latest tweet file: {latest_file}")
        return latest_file

    def extract_timestamp_from_filename(self, file_path: Path) -> Optional[str]:
        """Extract timestamp from filename."""
        match = re.search(r'_change_tweets_(\d{8}-\d{6})\.json$', file_path.name)
        return match.group(1) if match else None

    def is_thread(self, thread_tweets: List[Dict]) -> bool:
        """
        Determine if this is a thread (multiple parts) or a single tweet.
        
        Args:
            thread_tweets: List of tweets in the same thread_id
            
        Returns:
            True if this is a multi-part thread, False if single tweet
        """
        if not thread_tweets:
            return False
        
        # Check if there are multiple parts or if total_thread_parts > 1
        if len(thread_tweets) > 1:
            return True
        
        # Check if the single tweet has total_thread_parts > 1
        first_tweet = thread_tweets[0]
        total_parts = first_tweet.get("total_thread_parts", 1)
        return total_parts > 1

    async def create_thread(self, session: aiohttp.ClientSession, thread_tweets: List[Dict], account_id: int) -> Optional[str]:
        """
        Create a thread via thread API.
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweets in the thread (ordered by thread_part)
            account_id: Account ID for the thread
            
        Returns:
            thread_id if successful, None if failed
        """
        url = f"{self.api_base}/thread"
        
        # Extract text content from each tweet
        tweet_texts = []
        for tweet in thread_tweets:
            content = tweet.get("content_formatted", "")
            tweet_texts.append(content)
        
        # Use the thread_id from the tweet data
        thread_id = thread_tweets[0].get("thread_id")
        
        payload = {
            "account_id": account_id,
            "tweets": tweet_texts
            # "thread_id": thread_id
        }
        
        logger.info(f"Thread payload: {len(tweet_texts)} tweets, thread_id: {thread_id}")
        logger.info(f"Payload: {payload}")
        logger.info(f"Headers: {self.headers}")
        logger.info(f"URL: {url}")
        
        try:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 201:
                    data = await response.json()
                    logger.info(f"Response: {data}")
                    created_thread_id = data.get("thread_id")
                    created_tweets = data.get("tweets", [])
                    
                    logger.info(f"✅ Thread created successfully. ID: {created_thread_id} (Account: {account_id})")
                    logger.info(f"   Created {len(created_tweets)} tweets in thread")
                    
                    # Update the tweet data with the created IDs
                    for i, tweet_data in enumerate(thread_tweets):
                        if i < len(created_tweets):
                            tweet_data["twitter_id"] = created_tweets[i]["id"]
                            tweet_data["status"] = "created"
                    
                    return created_thread_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to create thread. Status: {response.status}")
                    logger.error(f"   Error: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Exception creating thread: {str(e)}")
            return None

    async def post_thread(self, session: aiohttp.ClientSession, thread_id: str) -> bool:
        """
        Post a thread via thread API.
        
        Args:
            session: aiohttp session
            thread_id: Thread ID to post
            
        Returns:
            True if successful, False if failed
        """
        url = f"{self.api_base}/thread/post/{thread_id}"

        logger.info(f"   Posting thread {thread_id}")
        logger.info(f"   Headers: {self.headers}")
        logger.info(f"   URL: {url}")

        try:
            async with session.post(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Response: {data}")
                    posted_count = data.get("posted", 0)
                    failed_count = data.get("failed", 0)
                    
                    logger.info(f"✅ Thread {thread_id} posted successfully")
                    logger.info(f"   Posted: {posted_count}, Failed: {failed_count}")
                    return posted_count > 0
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Failed to post thread {thread_id}. Status: {response.status}")
                    logger.warning(f"   Error: {error_text}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ Exception posting thread {thread_id}: {str(e)}")
            return False

    async def create_tweet(self, session: aiohttp.ClientSession, text: str, account_id: int) -> Optional[int]:
        """
        Create a single tweet via API.
        
        Args:
            session: aiohttp session
            text: Tweet content
            account_id: Account ID for the tweet
            
        Returns:
            tweet_id if successful, None if failed
        """
        url = f"{self.api_base}/tweet"
        payload = {
            "text": text,
            "account_id": account_id
        }
        logger.info("Tweet payload: ", payload)
        
        try:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 201:
                    data = await response.json()
                    tweet_id = data.get("tweet_id")
                    logger.info(f"✅ Tweet created successfully. ID: {tweet_id} (Account: {account_id})")
                    logger.info(f"   Content: {text[:100]}...")
                    return tweet_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to create tweet. Status: {response.status}")
                    logger.error(f"   Error: {error_text}")
                    logger.error(f"   Content: {text[:100]}...")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Exception creating tweet: {str(e)}")
            logger.error(f"   Content: {text[:100]}...")
            return None

    async def post_tweet(self, session: aiohttp.ClientSession, tweet_id: int) -> bool:
        """
        Post a single tweet via API.
        
        Args:
            session: aiohttp session
            tweet_id: ID of tweet to post
            
        Returns:
            True if successful, False if failed
        """
        url = f"{self.api_base}/tweet/post/{tweet_id}"
        
        try:
            async with session.post(url, headers=self.headers) as response:
                if response.status == 200:
                    logger.info(f"✅ Tweet {tweet_id} posted successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Failed to post tweet {tweet_id}. Status: {response.status}")
                    logger.warning(f"   Error: {error_text}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ Exception posting tweet {tweet_id}: {str(e)}")
            return False

    def load_tweet_data(self, file_path: Path) -> List[Dict]:
        """Load tweet data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"📄 Loaded {len(data)} tweets from {file_path}")
            return data
        except FileNotFoundError:
            logger.error(f"❌ File {file_path} not found")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parsing JSON from {file_path}: {str(e)}")
            return []

    def filter_tweets_by_section(self, tweets: List[Dict], section: str) -> List[Dict]:
        """Filter tweets by section (DOK4 or DOK3)."""
        return [tweet for tweet in tweets if tweet.get("section") == section]

    def group_tweets_by_thread(self, tweets: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group tweets by their thread_id.
        Each thread represents one logical posting unit.
        """
        thread_groups = {}
        
        for tweet in tweets:
            thread_id = tweet.get("thread_id")
            if thread_id:
                if thread_id not in thread_groups:
                    thread_groups[thread_id] = []
                thread_groups[thread_id].append(tweet)
        
        # Sort each thread by thread_part
        for thread_id in thread_groups:
            thread_groups[thread_id].sort(key=lambda x: x.get("thread_part", 1))
        
        return thread_groups

    def prioritize_tweets(self, tweets: List[Dict]) -> List[Dict]:
        """
        Prioritize tweets for posting:
        1. DOK4 over DOK3
        2. ADDED over UPDATED over DELETED
        3. Higher similarity scores for UPDATED tweets
        """
        def priority_score(tweet):
            section_score = 100 if tweet.get("section") == "DOK4" else 50
            
            change_type = tweet.get("change_type", "added")
            if change_type == "added":
                type_score = 30
            elif change_type == "updated":
                type_score = 20
                # Add similarity bonus for updates
                similarity = tweet.get("similarity_score", 0)
                type_score += similarity * 10
            else:  # deleted
                type_score = 10
            
            return section_score + type_score
        
        return sorted(tweets, key=priority_score, reverse=True)

    async def process_single_thread_for_user(self, session: aiohttp.ClientSession, 
                                           thread_tweets: List[Dict], 
                                           account_id: int) -> bool:
        """
        Process one complete thread or single tweet using appropriate APIs.
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweets in the thread
            account_id: Account ID for the tweets
            
        Returns:
            True if thread/tweet was successfully posted, False otherwise
        """
        if not thread_tweets:
            return False
            
        first_tweet = thread_tweets[0]
        section = first_tweet.get("section", "unknown")
        change_type = first_tweet.get("change_type", "unknown")
        thread_id = first_tweet.get("thread_id", "unknown")
        
        logger.info(f"🔄 Processing thread {thread_id}")
        logger.info(f"   Section: {section}, Change: {change_type}, Parts: {len(thread_tweets)}")
        
        # Add similarity info for updated tweets
        if change_type == "updated":
            similarity = first_tweet.get("similarity_score", 0)
            logger.info(f"   Similarity: {similarity:.0%}")
        
        # Determine if this is a thread or single tweet
        is_multi_part_thread = self.is_thread(thread_tweets)
        
        if is_multi_part_thread:
            logger.info(f"   🧵 Detected multi-part thread, using thread APIs")
            return await self.process_thread(session, thread_tweets, account_id)
        else:
            logger.info(f"   📝 Detected single tweet, using tweet APIs")
            return await self.process_single_tweet(session, thread_tweets[0], account_id)

    async def process_thread(self, session: aiohttp.ClientSession, 
                           thread_tweets: List[Dict], 
                           account_id: int) -> bool:
        """
        Process a multi-part thread using thread APIs.
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweets in the thread
            account_id: Account ID for the tweets
            
        Returns:
            True if thread was successfully posted, False otherwise
        """
        thread_id = thread_tweets[0].get("thread_id", "unknown")
        
        # Step 1: Create the thread
        logger.info(f"   Creating thread with {len(thread_tweets)} parts...")
        created_thread_id = await self.create_thread(session, thread_tweets, account_id)
        
        if not created_thread_id:
            logger.error(f"   ❌ Failed to create thread, skipping")
            return False
        
        logger.info(f"   ✅ Thread created successfully: {created_thread_id}")
        
        # Step 2: Post the thread
        logger.info(f"   Posting thread...")
        success = await self.post_thread(session, created_thread_id)
        
        if success:
            # Update all tweet statuses
            for tweet_data in thread_tweets:
                tweet_data["status"] = "posted"
                tweet_data["posted_at"] = datetime.now().isoformat()
            logger.info(f"   ✅ Thread posted successfully")
        else:
            # Update status to created but not posted
            for tweet_data in thread_tweets:
                if tweet_data.get("status") == "created":
                    tweet_data["status"] = "created_not_posted"
            logger.warning(f"   ⚠️ Thread created but posting failed")
        
        return success

    async def process_single_tweet(self, session: aiohttp.ClientSession, 
                                 tweet_data: Dict, 
                                 account_id: int) -> bool:
        """
        Process a single tweet using tweet APIs.
        
        Args:
            session: aiohttp session
            tweet_data: Single tweet data
            account_id: Account ID for the tweet
            
        Returns:
            True if tweet was successfully posted, False otherwise
        """
        content = tweet_data.get("content_formatted", "")
        
        # Step 1: Create the tweet
        logger.info(f"   Creating single tweet...")
        logger.info(f"   Content: {content[:100]}...")
        
        tweet_id = await self.create_tweet(session, content, account_id)
        
        if not tweet_id:
            logger.error(f"   ❌ Failed to create tweet, skipping")
            return False
        
        # Update the tweet data with the created ID
        tweet_data["twitter_id"] = tweet_id
        tweet_data["status"] = "created"
        
        logger.info(f"   ✅ Tweet created successfully: {tweet_id}")
        
        # Step 2: Post the tweet
        logger.info(f"   Posting tweet...")
        success = await self.post_tweet(session, tweet_id)
        
        if success:
            tweet_data["status"] = "posted"
            tweet_data["posted_at"] = datetime.now().isoformat()
            logger.info(f"   ✅ Tweet posted successfully")
        else:
            tweet_data["status"] = "created_not_posted"
            logger.warning(f"   ⚠️ Tweet created but posting failed")
        
        return success

    def load_historical_timeline(self) -> Dict:
        """Load complete historical timeline from all sessions."""
        timeline_file = Path("demo/data/complete_timeline.json")
        
        if timeline_file.exists():
            try:
                with open(timeline_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("⚠️ Could not load historical timeline, creating new one")
        
        # Return empty timeline structure
        return {
            "timeline_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "sessions": [],
            "all_tweets": [],
            "users": {},
            "statistics": {
                "total_runs": 0,
                "total_tweets": 0,
                "total_users": 0,
                "date_range": {
                    "first_run": None,
                    "last_run": None
                },
                "change_types": {
                    "added": 0,
                    "updated": 0,
                    "deleted": 0
                }
            }
        }

    def update_historical_timeline(self, new_session_data: Dict, posting_results: Dict):
        """Update the complete historical timeline with new session data."""
        timeline = self.load_historical_timeline()
        
        user_name = new_session_data["session"]["user"]
        session_id = new_session_data["session"]["id"]
        session_tweets = new_session_data["tweets"]
        
        # Add session to timeline
        session_metadata = {
            "session_id": session_id,
            "user": user_name,
            "timestamp": new_session_data["session"]["timestamp"],
            "run_number": new_session_data["session"]["run_number"],
            "tweets_count": len(session_tweets),
            "change_summary": new_session_data["session"]["change_summary"],
            "posting_results": {
                "attempted": posting_results.get("tweets_posted", 0),
                "successful": posting_results.get("tweets_posted", 0),
                "failed": 0,
                "thread_id": posting_results.get("thread_posted"),
                "status": posting_results.get("status")
            }
        }
        
        timeline["sessions"].append(session_metadata)
        
        # Add tweets to timeline with posting status
        for tweet in session_tweets:
            # Update tweet with posting information
            if posting_results.get("status") == "success":
                tweet["status"]["posting_session"] = session_id
                if tweet["metadata"]["thread_id"] == posting_results.get("thread_posted"):
                    tweet["status"]["current"] = "posted"
                    tweet["timestamps"]["posted_at"] = datetime.now().isoformat()
            
            timeline["all_tweets"].append(tweet)
        
        # Update user statistics
        if user_name not in timeline["users"]:
            timeline["users"][user_name] = {
                "username": new_session_data["user_info"]["username"],
                "display_name": new_session_data["user_info"]["display_name"],
                "handle": new_session_data["user_info"]["handle"],
                "avatar": new_session_data["user_info"]["avatar"],
                "total_tweets": 0,
                "total_posted": 0,
                "sessions": [],
                "last_updated": session_id,
                "change_breakdown": {
                    "added": 0,
                    "updated": 0,
                    "deleted": 0
                },
                "first_seen": session_id
            }
        
        user_stats = timeline["users"][user_name]
        user_stats["total_tweets"] += len(session_tweets)
        user_stats["sessions"].append(session_id)
        user_stats["last_updated"] = session_id
        
        # Update change breakdowns
        for change_type, count in new_session_data["session"]["change_summary"].items():
            user_stats["change_breakdown"][change_type] += count
            timeline["statistics"]["change_types"][change_type] += count
        
        if posting_results.get("status") == "success":
            user_stats["total_posted"] += posting_results.get("tweets_posted", 0)
        
        # Update global statistics
        timeline["statistics"]["total_runs"] += 1
        timeline["statistics"]["total_tweets"] += len(session_tweets)
        timeline["statistics"]["total_users"] = len(timeline["users"])
        timeline["last_updated"] = datetime.now().isoformat()
        
        # Update date range
        if timeline["statistics"]["date_range"]["first_run"] is None:
            timeline["statistics"]["date_range"]["first_run"] = session_id
        timeline["statistics"]["date_range"]["last_run"] = session_id
        
        # Save updated timeline
        timeline_file = Path("demo/data/complete_timeline.json")
        timeline_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(timeline_file, 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 Historical timeline updated with session {session_id}")
        return timeline

    def load_session_data(self, user_name: str) -> Optional[Dict]:
        """Load the latest session data for a user."""
        demo_dir = Path("demo/data")
        if not demo_dir.exists():
            return None
        
        # Find latest session file for user
        pattern = f"session_*_{user_name}.json"
        session_files = list(demo_dir.glob(pattern))
        
        if not session_files:
            logger.warning(f"⚠️ No session data found for {user_name}")
            return None
        
        # Sort by timestamp and get latest
        session_files.sort(key=lambda x: x.name, reverse=True)
        latest_file = session_files[0]
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"❌ Error loading session data from {latest_file}: {e}")
            return None

    async def process_user(self, session: aiohttp.ClientSession, user_name: str) -> Dict:
        """
        Process tweets for a specific user with demo data integration.
        """
        logger.info(f"{'='*50}")
        logger.info(f"PROCESSING USER: {user_name}")
        logger.info(f"{'='*50}")
        
        # Get account ID
        account_id = self.get_account_id(user_name)
        if not account_id:
            logger.error(f"❌ No account ID mapping found for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No account ID mapping'
            }
        
        logger.info(f"🎯 Account ID: {account_id}")
        
        # Load session data (from test_workflowy.py output)
        session_data = self.load_session_data(user_name)
        
        if not session_data:
            # Fallback to old method
            tweet_file = self.find_latest_tweet_file(user_name)
            if not tweet_file:
                logger.error(f"❌ No tweet files or session data found for user: {user_name}")
                return {
                    'user': user_name,
                    'status': 'error',
                    'error': 'No tweet files or session data found'
                }
            
            # Load old format
            all_tweets = self.load_tweet_data(tweet_file)
            timestamp = self.extract_timestamp_from_filename(tweet_file)
        else:
            # Use new session data format
            all_tweets = session_data["tweets"]
            timestamp = session_data["session"]["timestamp"]
            logger.info(f"📅 Processing session: {timestamp} (Run #{session_data['session']['run_number']})")
        
        if not all_tweets:
            logger.error(f"❌ No tweet data loaded for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No tweet data loaded'
            }
        
        # Check data format and convert if necessary
        compatible_tweets = []
        first_tweet = all_tweets[0] if all_tweets else {}
        
        # Detect format: new format has nested 'metadata' and 'content', old format has flat structure
        if 'metadata' in first_tweet and 'content' in first_tweet:
            # New session data format - convert to old format for compatibility
            logger.info(f"📋 Detected new session data format, converting...")
            for tweet in all_tweets:
                compatible_tweet = {
                    "id": tweet["id"],
                    "section": tweet["metadata"]["section"],
                    "change_type": tweet["metadata"]["change_type"],
                    "content_formatted": tweet["content"]["text"],
                    "thread_id": tweet["metadata"]["thread_id"],
                    "thread_part": tweet["metadata"]["thread_part"],
                    "total_thread_parts": tweet["metadata"].get("total_thread_parts", 1),
                    "similarity_score": tweet["metadata"].get("similarity_score"),
                    "change_details": tweet["metadata"].get("change_details")
                }
                compatible_tweets.append(compatible_tweet)
        else:
            # Old format - use as is
            logger.info(f"📋 Detected old tweet data format, using as is...")
            compatible_tweets = all_tweets
        
        # Continue with existing logic using compatible_tweets
        # Show content summary
        dok4_tweets = self.filter_tweets_by_section(compatible_tweets, "DOK4")
        dok3_tweets = self.filter_tweets_by_section(compatible_tweets, "DOK3")
        
        logger.info(f"📊 Content Summary:")
        logger.info(f"   DOK4 tweets: {len(dok4_tweets)}")
        logger.info(f"   DOK3 tweets: {len(dok3_tweets)}")
        
        # Show change type breakdown
        change_summary = {}
        for tweet in compatible_tweets:
            change_type = tweet.get("change_type", "unknown")
            change_summary[change_type] = change_summary.get(change_type, 0) + 1
        
        logger.info(f"   Change types: {change_summary}")
        
        # Group tweets by thread and prioritize
        thread_groups = self.group_tweets_by_thread(compatible_tweets)
        
        if not thread_groups:
            logger.error(f"❌ No valid threads found for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No valid threads found'
            }
        
        # Get all main tweets (first part of each thread) and prioritize them
        main_tweets = []
        for thread_id, thread_tweets in thread_groups.items():
            if thread_tweets:
                main_tweets.append(thread_tweets[0])  # First part of thread
        
        prioritized_main_tweets = self.prioritize_tweets(main_tweets)
        
        if not prioritized_main_tweets:
            logger.error(f"❌ No tweets to post for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No tweets to post'
            }
        
        if self.posting_mode == "single":
            # Post only the highest priority thread (current behavior)
            top_tweet = prioritized_main_tweets[0]
            top_thread_id = top_tweet.get("thread_id")
            top_thread_tweets = thread_groups[top_thread_id]
            
            logger.info(f"🎯 SINGLE MODE: Selected thread: {top_thread_id}")
            logger.info(f"   Section: {top_tweet.get('section')}")
            logger.info(f"   Change type: {top_tweet.get('change_type')}")
            logger.info(f"   Parts: {len(top_thread_tweets)}")
            
            success = await self.process_single_thread_for_user(session, top_thread_tweets, account_id)
            
            # Prepare results for single mode
            results = {
                'user': user_name,
                'account_id': account_id,
                'status': 'success' if success else 'partial_success',
                'tweets_posted': len(top_thread_tweets) if success else 0,
                'threads_posted': 1 if success else 0,
                'section_used': top_tweet.get('section'),
                'change_type': top_tweet.get('change_type'),
                'thread_posted': top_thread_id if success else None,
                'total_available_threads': len(thread_groups),
                'session_id': timestamp,
                'posting_mode': 'single'
            }
            
        else:  # posting_mode == "all"
            # Post all threads
            logger.info(f"🚀 ALL MODE: Processing {len(prioritized_main_tweets)} threads")
            
            successful_threads = []
            failed_threads = []
            total_tweets_posted = 0
            
            for i, main_tweet in enumerate(prioritized_main_tweets, 1):
                thread_id = main_tweet.get("thread_id")
                thread_tweets = thread_groups[thread_id]
                
                logger.info(f"      🧵 Thread {i}/{len(prioritized_main_tweets)}: {thread_id}")
                logger.info(f"      Section: {main_tweet.get('section')}")
                logger.info(f"      Change type: {main_tweet.get('change_type')}")
                logger.info(f"      Parts: {len(thread_tweets)}")
                
                if main_tweet.get('change_type') == 'updated':
                    similarity = main_tweet.get('similarity_score', 0)
                    logger.info(f"      Similarity: {similarity:.0%}")
                
                success = await self.process_single_thread_for_user(session, thread_tweets, account_id)
                
                if success:
                    successful_threads.append(thread_id)
                    total_tweets_posted += len(thread_tweets)
                    logger.info(f"      ✅ Thread {thread_id} posted successfully")
                else:
                    failed_threads.append(thread_id)
                    logger.warning(f"      ❌ Thread {thread_id} failed to post")
                
                # Add delay between threads (except for the last one)
                if i < len(prioritized_main_tweets):
                    logger.info(f"      ⏱️ Waiting 5 seconds before next thread...")
                    await asyncio.sleep(5)
            
            # Prepare results for all mode
            all_success = len(failed_threads) == 0
            partial_success = len(successful_threads) > 0 and len(failed_threads) > 0
            
            results = {
                'user': user_name,
                'account_id': account_id,
                'status': 'success' if all_success else ('partial_success' if partial_success else 'error'),
                'tweets_posted': total_tweets_posted,
                'threads_posted': len(successful_threads),
                'threads_failed': len(failed_threads),
                'successful_threads': successful_threads,
                'failed_threads': failed_threads,
                'total_available_threads': len(thread_groups),
                'session_id': timestamp,
                'posting_mode': 'all'
            }
            
            logger.info(f"\n📊 ALL MODE SUMMARY for {user_name}:")
            logger.info(f"   ✅ Successful threads: {len(successful_threads)}")
            logger.info(f"   ❌ Failed threads: {len(failed_threads)}")
            logger.info(f"   📝 Total tweets posted: {total_tweets_posted}")
        
        # Update historical timeline if we have session data
        if session_data:
            try:
                self.update_historical_timeline(session_data, results)
                logger.info(f"📊 Historical timeline updated for {user_name}")
            except Exception as e:
                logger.error(f"⚠️ Failed to update historical timeline: {e}")
        
        # Save updated tweet data back to file (maintain backward compatibility)
        # user_dir = self.users_dir / user_name
        # timestamp_str = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        # updated_file = user_dir / f"{user_name}_change_tweets_updated_{timestamp_str}.json"
        
        # with open(updated_file, 'w', encoding='utf-8') as f:
        #     json.dump(compatible_tweets, f, indent=2, ensure_ascii=False)
        # logger.info(f"💾 Updated tweet data saved to {updated_file}")
        
        return results

    async def run(self, target_users: Optional[List[str]] = None, posting_mode: str = None):
        """
        Main execution function.
        
        Args:
            target_users: List of specific users to process. If None, process all available users.
            posting_mode: Override the instance posting mode if provided.
        """
        # Use provided posting_mode or fall back to instance mode
        effective_mode = posting_mode or self.posting_mode
        
        logger.info(f"🎬 Starting Tweet Posting Process (Change-based) - Mode: {effective_mode.upper()}")
        logger.info("=" * 50)
        
        # Determine which users to process
        available_users = self.get_available_users()
        
        if not available_users:
            logger.error("❌ No users found with valid account ID mappings")
            return
        
        if target_users:
            # Filter to only requested users that are available
            users_to_process = [user for user in target_users if user in available_users]
            if not users_to_process:
                logger.error(f"❌ None of the requested users {target_users} are available")
                logger.info(f"Available users: {available_users}")
                return
        else:
            users_to_process = available_users
        
        logger.info(f"👥 Users to process: {users_to_process}")
        logger.info(f"📂 Users directory: {self.users_dir}")
        
        # Create aiohttp session
        timeout = aiohttp.ClientTimeout(total=30)
        results = []
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for user_name in users_to_process:
                result = await self.process_user(session, user_name)
                results.append(result)
                
                # Add delay between users
                if user_name != users_to_process[-1]:  # Not the last user
                    logger.info(f"⏱️ Waiting 3 seconds before next user...")
                    await asyncio.sleep(3)
        
        # Final summary
        logger.info("\n" + "=" * 50)
        logger.info("🏁 FINAL SUMMARY")
        logger.info("=" * 50)
        
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'error']
        partial = [r for r in results if r['status'] == 'partial_success']
        
        logger.info(f"✅ Successful users: {len(successful)}/{len(results)}")
        logger.info(f"⚠️ Partial success users: {len(partial)}/{len(results)}")
        logger.info(f"❌ Failed users: {len(failed)}/{len(results)}")
        
        if successful:
            logger.info(f"\n📊 SUCCESS DETAILS:")
            for result in successful:
                mode = result.get('posting_mode', 'unknown')
                if mode == 'single':
                    section = result.get('section_used', 'unknown')
                    change_type = result.get('change_type', 'unknown')
                    tweets_posted = result.get('tweets_posted', 0)
                    total_threads = result.get('total_available_threads', 0)
                    logger.info(f"  {result['user']} (Account {result['account_id']}): {tweets_posted} tweets posted")
                    logger.info(f"    SINGLE MODE: {section} {change_type} thread (1/{total_threads} available)")
                else:  # all mode
                    threads_posted = result.get('threads_posted', 0)
                    tweets_posted = result.get('tweets_posted', 0)
                    total_threads = result.get('total_available_threads', 0)
                    logger.info(f"  {result['user']} (Account {result['account_id']}): {tweets_posted} tweets in {threads_posted} threads")
                    logger.info(f"    ALL MODE: {threads_posted}/{total_threads} threads posted successfully")
        
        if partial:
            logger.info(f"\n⚠️ PARTIAL SUCCESS DETAILS:")
            for result in partial:
                threads_posted = result.get('threads_posted', 0)
                threads_failed = result.get('threads_failed', 0)
                tweets_posted = result.get('tweets_posted', 0)
                logger.info(f"  {result['user']} (Account {result['account_id']}): {tweets_posted} tweets posted")
                logger.info(f"    {threads_posted} threads succeeded, {threads_failed} threads failed")
        
        if failed:
            logger.info(f"\n❌ FAILURE DETAILS:")
            for result in failed:
                logger.info(f"  {result['user']}: {result['error']}")
        
        total_tweets = sum(r.get('tweets_posted', 0) for r in successful + partial)
        total_threads = sum(r.get('threads_posted', 0) for r in successful + partial)
        
        if self.posting_mode == "single":
            logger.info(f"\n🎉 GRAND TOTAL: {total_tweets} tweets posted (1 priority thread per account)!")
        else:
            logger.info(f"\n🎉 GRAND TOTAL: {total_tweets} tweets in {total_threads} threads posted!")
    
    def load_latest_tweets_from_aws(self, user_name: str) -> List[Dict]:
        """
        Load latest tweets from S3 instead of local files
        """
        try:
            # List objects in S3 to find latest file
            response = self.storage.s3.list_objects_v2(
                Bucket=self.storage.bucket_name,
                Prefix=f"change_tweets/{user_name}/",
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                print(f"📄 No tweet files found in S3 for {user_name}")
                return []
            
            # Sort by last modified and get latest
            latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
            
            # Get the latest tweets file
            obj = self.storage.s3.get_object(
                Bucket=self.storage.bucket_name,
                Key=latest_object['Key']
            )
            
            tweets_data = json.loads(obj['Body'].read())
            print(f"📄 Loaded {len(tweets_data)} tweets from S3: {latest_object['Key']}")
            return tweets_data
            
        except Exception as e:
            print(f"❌ Error loading tweets from AWS for {user_name}: {e}")
            return []

    def save_updated_tweets_to_aws(self, user_name: str, tweets: List[Dict]):
        """
        Save updated tweet data back to S3 after posting
        """
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Save with updated status
            updated_url = self.storage.save_change_tweets(user_name, tweets, f"{timestamp}_updated")
            print(f"📄 Updated tweet statuses saved to S3: {updated_url}")
            
        except Exception as e:
            print(f"❌ Error saving updated tweets to AWS for {user_name}: {e}")

def preview_what_will_be_posted(target_users: Optional[List[str]] = None, posting_mode: str = "single"):
    """Preview which tweets will be posted without actually posting them."""
    poster = TweetPoster(posting_mode=posting_mode)
    
    mode_desc = "1 priority thread per account" if posting_mode == "single" else "ALL threads per account"
    print(f"👀 PREVIEW: What will be posted ({mode_desc}) - Mode: {posting_mode.upper()}")
    print("=" * 50)
    
    available_users = poster.get_available_users()
    
    if target_users:
        users_to_preview = [user for user in target_users if user in available_users]
    else:
        users_to_preview = available_users
    
    if not users_to_preview:
        print("❌ No users available for preview")
        return
    
    for user_name in users_to_preview:
        account_id = poster.get_account_id(user_name)
        print(f"\n👤 USER: {user_name} (Account ID: {account_id})")
        print("-" * 30)
        
        # Find latest tweet file
        tweet_file = poster.find_latest_tweet_file(user_name)
        
        if not tweet_file:
            print(f"❌ No tweet files found for {user_name}")
            continue
        
        timestamp = poster.extract_timestamp_from_filename(tweet_file)
        print(f"📅 Latest file: {tweet_file.name} ({timestamp})")
        
        # Load and analyze tweets
        all_tweets = poster.load_tweet_data(tweet_file)
        
        if not all_tweets:
            print(f"❌ No tweets in file for {user_name}")
            continue
        
        # Show content summary
        dok4_tweets = poster.filter_tweets_by_section(all_tweets, "DOK4")
        dok3_tweets = poster.filter_tweets_by_section(all_tweets, "DOK3")
        
        print(f"\n📊 Content Summary:")
        print(f"   DOK4 tweets: {len(dok4_tweets)}")
        print(f"   DOK3 tweets: {len(dok3_tweets)}")
        
        # Show change types
        change_summary = {}
        for tweet in all_tweets:
            change_type = tweet.get("change_type", "unknown")
            change_summary[change_type] = change_summary.get(change_type, 0) + 1
        
        print(f"   Change types: {change_summary}")
        
        # Show what will be posted
        thread_groups = poster.group_tweets_by_thread(all_tweets)
        
        if thread_groups:
            # Get prioritized threads
            main_tweets = []
            for thread_id, thread_tweets in thread_groups.items():
                if thread_tweets:
                    main_tweets.append(thread_tweets[0])
            
            prioritized_main_tweets = poster.prioritize_tweets(main_tweets)
            
            if prioritized_main_tweets:
                top_tweet = prioritized_main_tweets[0]
                top_thread_id = top_tweet.get("thread_id")
                top_thread_tweets = thread_groups[top_thread_id]
                
                print(f"\n🎯 Will post TOP PRIORITY thread:")
                print(f"   Thread ID: {top_thread_id}")
                print(f"   Section: {top_tweet.get('section')}")
                print(f"   Change type: {top_tweet.get('change_type')}")
                print(f"   Parts: {len(top_thread_tweets)}")
                
                if top_tweet.get('change_type') == 'updated':
                    similarity = top_tweet.get('similarity_score', 0)
                    print(f"   Similarity: {similarity:.0%}")
                
                print(f"\n   Content preview:")
                for i, tweet in enumerate(top_thread_tweets, 1):
                    content = tweet.get("content_formatted", "")
                    print(f"      Part {i}: {content[:80]}...")
                    print(f"               Characters: {len(content)}")
                
                print(f"\n   Available threads: {len(thread_groups)} total")
            else:
                print(f"\n❌ No valid threads found for {user_name}")
        else:
            print(f"\n❌ No threads available for {user_name}")

async def main():
    """Main function with options."""
    import sys
    
    args = sys.argv[1:]
    posting_mode = "single"  # default
    target_users = []
    
    # Parse command line arguments
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--mode" and i + 1 < len(args):
            posting_mode = args[i + 1]
            if posting_mode not in ["single", "all"]:
                print(f"❌ Invalid posting mode: {posting_mode}. Must be 'single' or 'all'")
                return
            i += 2
        elif arg == "preview":
            # Handle preview mode
            preview_users = args[i+1:] if i+1 < len(args) else None
            preview_what_will_be_posted(preview_users, posting_mode)
            return
        else:
            target_users.append(arg)
            i += 1
    
    # Create poster with specified mode
    poster = TweetPoster(posting_mode=posting_mode)
    await poster.run(target_users if target_users else None)

if __name__ == "__main__":
    print("Tweet Poster for DOK Content (Change Detection)")
    print("Usage:")
    print("  python post_tweets.py --mode single [user1] [user2]     # Post 1 priority thread per account (default)")
    print("  python post_tweets.py --mode all [user1] [user2]        # Post all threads for each account")
    print("  python post_tweets.py preview --mode single [user1]     # Preview single mode")
    print("  python post_tweets.py preview --mode all [user1]        # Preview all mode")
    print("  python post_tweets.py [user1] [user2]                   # Default to single mode")
    print("  python post_tweets.py                                   # Process all users in single mode")
    print()
    print("Posting Modes:")
    print("  single: Post only the highest priority thread per user (current behavior)")
    print("  all:    Post all available threads per user with 5-second delays")
    print()
    print("Available users and account IDs:")
    for user, account_id in USER_ACCOUNT_MAPPING.items():
        print(f"  {user}: Account {account_id}")
    print()
    
    asyncio.run(main())