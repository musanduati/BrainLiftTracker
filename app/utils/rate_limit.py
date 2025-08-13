import time
import threading
from collections import defaultdict
from app.core.config import Config

# Rate limiting for Twitter API
# Twitter allows 200 tweets per 15 minutes per user
rate_limit_tracker = {
    'accounts': defaultdict(lambda: {'count': 0, 'reset_time': 0}),
    'lock': threading.Lock()
}

def check_rate_limit(account_id):
    """Check if we can post for this account without hitting rate limits"""
    with rate_limit_tracker['lock']:
        current_time = time.time()
        account_limits = rate_limit_tracker['accounts'][account_id]
        
        # Reset counter if 15 minutes have passed
        if current_time > account_limits['reset_time']:
            account_limits['count'] = 0
            account_limits['reset_time'] = current_time + Config.RATE_LIMIT_WINDOW
        
        # Check if we've hit the limit (leave some buffer)
        if account_limits['count'] >= Config.RATE_LIMIT_TWEETS_PER_15MIN:
            wait_time = account_limits['reset_time'] - current_time
            return False, wait_time
        
        # Increment counter
        account_limits['count'] += 1
        return True, 0

def get_rate_limit_delay(account_id):
    """Get the remaining time until rate limit resets for an account"""
    with rate_limit_tracker['lock']:
        current_time = time.time()
        account_limits = rate_limit_tracker['accounts'][account_id]
        
        if current_time > account_limits['reset_time']:
            return 0
        
        if account_limits['count'] >= Config.RATE_LIMIT_TWEETS_PER_15MIN:
            return account_limits['reset_time'] - current_time
        
        return 0

def get_rate_limit_status(account_id):
    """Get current rate limit status for an account"""
    with rate_limit_tracker['lock']:
        current_time = time.time()
        account_limits = rate_limit_tracker['accounts'][account_id]
        
        # Reset counter if 15 minutes have passed
        if current_time > account_limits['reset_time']:
            account_limits['count'] = 0
            account_limits['reset_time'] = current_time + Config.RATE_LIMIT_WINDOW
        
        return {
            'tweets_posted': account_limits['count'],
            'limit': Config.RATE_LIMIT_TWEETS_PER_15MIN,
            'reset_in_seconds': max(0, account_limits['reset_time'] - current_time) if account_limits['reset_time'] > current_time else 0
        }