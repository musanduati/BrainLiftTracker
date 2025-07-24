import json
import asyncio
import aiohttp
from typing import List, Dict, Optional
from pathlib import Path
import logging
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User to Account ID mapping
USER_ACCOUNT_MAPPING = {
    # "sanket_ghia": 2,
    # "musa_nduati": 3,
    "yuki_tanaka": 3,
    # "elijah_johnson": 5,
    # Add more users as needed
}

class TweetPoster:
    def __init__(self):
        self.api_base = "http://localhost:5555/api/v1"
        self.api_key = "2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb"
        # self.api_base = "http://51.44.57.211/api/v1"
        # self.api_key = "caa7bb2537d7b2e71eaaff143202a8cd50fa767fc2a65467b6bc9dafc88f4db5"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.users_dir = Path("users")

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

    async def create_tweet(self, session: aiohttp.ClientSession, text: str, account_id: int) -> Optional[int]:
        """
        Create a tweet via API.
        
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
        Post a tweet via API.
        
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
        Process one complete thread (which may be multiple parts).
        
        Args:
            session: aiohttp session
            thread_tweets: List of tweets in the thread
            account_id: Account ID for the tweets
            
        Returns:
            True if thread was successfully posted, False otherwise
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
        
        created_tweet_ids = []
        
        # Step 1: Create all tweets in this thread
        for i, tweet_data in enumerate(thread_tweets, 1):
            content = tweet_data.get("content_formatted", "")
            logger.info(f"   Creating part {i}/{len(thread_tweets)}...")
            logger.info(f"   Content: {content[:100]}...")
            
            tweet_id = await self.create_tweet(session, content, account_id)
            if tweet_id:
                created_tweet_ids.append(tweet_id)
                # Update the tweet data with the created ID
                tweet_data["twitter_id"] = tweet_id
                tweet_data["status"] = "created"
            else:
                logger.error(f"   ❌ Failed to create part {i}, skipping this thread")
                return False
        
        logger.info(f"   ✅ All {len(created_tweet_ids)} parts created successfully")
        
        # Step 2: Post all tweets
        success_count = 0
        for i, (tweet_id, tweet_data) in enumerate(zip(created_tweet_ids, thread_tweets), 1):
            logger.info(f"   Posting part {i}/{len(created_tweet_ids)}...")
            
            success = await self.post_tweet(session, tweet_id)
            if success:
                success_count += 1
                tweet_data["status"] = "posted"
                tweet_data["posted_at"] = datetime.now().isoformat()
            else:
                tweet_data["status"] = "created_not_posted"
        
        logger.info(f"   📊 Posted {success_count}/{len(created_tweet_ids)} parts successfully")
        
        # Consider success if we created the tweets
        return len(created_tweet_ids) > 0

    async def process_user(self, session: aiohttp.ClientSession, user_name: str) -> Dict:
        """
        Process tweets for a specific user.
        
        Args:
            session: aiohttp session
            user_name: Name of the user to process
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"\n{'='*50}")
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
        
        # Find latest tweet file
        tweet_file = self.find_latest_tweet_file(user_name)
        
        if not tweet_file:
            logger.error(f"❌ No tweet files found for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No tweet files found'
            }
        
        # Get timestamp from filename
        timestamp = self.extract_timestamp_from_filename(tweet_file)
        logger.info(f"📅 Processing tweets from: {timestamp}")
        
        # Load all tweet data
        all_tweets = self.load_tweet_data(tweet_file)
        
        if not all_tweets:
            logger.error(f"❌ No tweet data loaded for user: {user_name}")
            return {
                'user': user_name,
                'status': 'error',
                'error': 'No tweet data loaded'
            }
        
        # Show content summary
        dok4_tweets = self.filter_tweets_by_section(all_tweets, "DOK4")
        dok3_tweets = self.filter_tweets_by_section(all_tweets, "DOK3")
        
        logger.info(f"📊 Content Summary:")
        logger.info(f"   DOK4 tweets: {len(dok4_tweets)}")
        logger.info(f"   DOK3 tweets: {len(dok3_tweets)}")
        
        # Show change type breakdown
        change_summary = {}
        for tweet in all_tweets:
            change_type = tweet.get("change_type", "unknown")
            change_summary[change_type] = change_summary.get(change_type, 0) + 1
        
        logger.info(f"   Change types: {change_summary}")
        
        # Group tweets by thread and prioritize
        thread_groups = self.group_tweets_by_thread(all_tweets)
        
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
        
        # Post only the highest priority thread
        top_tweet = prioritized_main_tweets[0]
        top_thread_id = top_tweet.get("thread_id")
        top_thread_tweets = thread_groups[top_thread_id]
        
        logger.info(f"🎯 Selected thread: {top_thread_id}")
        logger.info(f"   Section: {top_tweet.get('section')}")
        logger.info(f"   Change type: {top_tweet.get('change_type')}")
        logger.info(f"   Parts: {len(top_thread_tweets)}")
        
        success = await self.process_single_thread_for_user(session, top_thread_tweets, account_id)
        
        # Save updated tweet data back to file
        user_dir = self.users_dir / user_name
        timestamp_str = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        updated_file = user_dir / f"{user_name}_change_tweets_updated_{timestamp_str}.json"
        
        with open(updated_file, 'w', encoding='utf-8') as f:
            json.dump(all_tweets, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Updated tweet data saved to {updated_file}")
        
        return {
            'user': user_name,
            'account_id': account_id,
            'status': 'success' if success else 'partial_success',
            'tweets_posted': len(top_thread_tweets) if success else 0,
            'section_used': top_tweet.get('section'),
            'change_type': top_tweet.get('change_type'),
            'thread_posted': top_thread_id if success else None,
            'total_available_threads': len(thread_groups),
            'file_processed': str(tweet_file)
        }

    async def run(self, target_users: Optional[List[str]] = None):
        """
        Main execution function.
        
        Args:
            target_users: List of specific users to process. If None, process all available users.
        """
        logger.info("🎬 Starting Tweet Posting Process (Change-based)")
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
        
        logger.info(f"✅ Successful users: {len(successful)}/{len(results)}")
        logger.info(f"❌ Failed users: {len(failed)}/{len(results)}")
        
        if successful:
            logger.info(f"\n📊 SUCCESS DETAILS:")
            for result in successful:
                section = result.get('section_used', 'unknown')
                change_type = result.get('change_type', 'unknown')
                tweets_posted = result.get('tweets_posted', 0)
                total_threads = result.get('total_available_threads', 0)
                logger.info(f"  {result['user']} (Account {result['account_id']}): {tweets_posted} tweets posted")
                logger.info(f"    {section} {change_type} thread (1/{total_threads} available threads)")
        
        if failed:
            logger.info(f"\n❌ FAILURE DETAILS:")
            for result in failed:
                logger.info(f"  {result['user']}: {result['error']}")
        
        total_tweets = sum(r.get('tweets_posted', 0) for r in successful)
        logger.info(f"\n🎉 GRAND TOTAL: {total_tweets} tweets posted (1 priority thread per account)!")

def preview_what_will_be_posted(target_users: Optional[List[str]] = None):
    """Preview which tweets will be posted without actually posting them."""
    poster = TweetPoster()
    
    print("👀 PREVIEW: What will be posted (1 priority thread per account)")
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
    
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        # Preview mode
        target_users = sys.argv[2:] if len(sys.argv) > 2 else None
        preview_what_will_be_posted(target_users)
    else:
        # Posting mode
        target_users = sys.argv[1:] if len(sys.argv) > 1 else None
        poster = TweetPoster()
        await poster.run(target_users)

if __name__ == "__main__":
    print("Tweet Poster for DOK Content (Change Detection)")
    print("Usage:")
    print("  python post_tweets.py preview [user1] [user2]  # Preview what will be posted")
    print("  python post_tweets.py [user1] [user2]          # Post tweets for specific users")
    print("  python post_tweets.py                          # Post tweets for all users")
    print()
    print("Available users and account IDs:")
    for user, account_id in USER_ACCOUNT_MAPPING.items():
        print(f"  {user}: Account {account_id}")
    print()
    
    asyncio.run(main())