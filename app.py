from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
import hashlib
from datetime import datetime, timedelta, timezone
# For backward compatibility with older Python versions
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
import json
import requests
# tweepy import moved to where it's used for Python 3.13 compatibility
import secrets
import base64
import urllib.parse
from cryptography.fernet import Fernet
import uuid
import threading
import time
from collections import defaultdict

app = Flask(__name__)
# Enable CORS for the frontend
CORS(app, origins=[
    "http://localhost:5173", 
    "http://localhost:5174", 
    "http://localhost:5175",
    "http://localhost:3000",
    "http://98.86.153.32",  # Lightsail IP
    "*"  # Allow all origins in production - adjust based on your security needs
], supports_credentials=True)

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'twitter_manager.db')

# Ensure instance directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# API key from environment
VALID_API_KEY = os.environ.get('API_KEY')
if not VALID_API_KEY:
    print("WARNING: No API_KEY found in environment. Please set it in .env file.")
    print("For testing, you can use: 2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb")
    VALID_API_KEY = "test-api-key-replace-in-production"

# Get encryption key from environment
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    print("WARNING: No ENCRYPTION_KEY found in environment. Please set it in .env file.")
    print("Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    # Use a default for testing only - NEVER use in production
    ENCRYPTION_KEY = Fernet.generate_key().decode()
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# Twitter API credentials
TWITTER_CLIENT_ID = os.environ.get('TWITTER_CLIENT_ID')
TWITTER_CLIENT_SECRET = os.environ.get('TWITTER_CLIENT_SECRET')

if not TWITTER_CLIENT_ID or not TWITTER_CLIENT_SECRET:
    print("WARNING: Twitter API credentials not found in environment.")
    print("Please set TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET in .env file.")
    print("Get these from: https://developer.twitter.com/en/portal/dashboard")
TWITTER_CALLBACK_URL = os.environ.get('TWITTER_CALLBACK_URL', 'http://localhost:5555/auth/callback')

if 'localhost' in TWITTER_CALLBACK_URL and os.environ.get('FLASK_ENV') == 'production':
    print("WARNING: Using localhost callback URL in production environment!")
    print("Please set TWITTER_CALLBACK_URL in .env file to your server's address.")

# Mock mode disabled - we want real Twitter posting
MOCK_TWITTER_POSTING = False

# Allow runtime toggle
mock_mode_override = {'enabled': False}

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
            account_limits['reset_time'] = current_time + 900  # 15 minutes
        
        # Check if we've hit the limit (leave some buffer)
        if account_limits['count'] >= 180:  # Leave buffer of 20 tweets
            wait_time = account_limits['reset_time'] - current_time
            return False, wait_time
        
        # Increment counter
        account_limits['count'] += 1
        return True, 0

def get_rate_limit_delay(account_id):
    """Get recommended delay based on current rate for this account"""
    with rate_limit_tracker['lock']:
        account_limits = rate_limit_tracker['accounts'][account_id]
        tweets_posted = account_limits['count']
        
        # Progressive delays based on usage
        if tweets_posted < 50:
            return 1  # 1 second delay for first 50 tweets
        elif tweets_posted < 100:
            return 2  # 2 seconds for tweets 50-100
        elif tweets_posted < 150:
            return 3  # 3 seconds for tweets 100-150
        else:
            return 5  # 5 seconds when approaching limit

def get_db():
    """Get database connection with timeout and WAL mode for better concurrency"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # 30 second timeout
    conn.row_factory = sqlite3.Row
    return conn

def check_api_key():
    """Simple API key check"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        api_key = request.args.get('api_key')
    
    if api_key != VALID_API_KEY:
        return False
    return True

def decrypt_token(encrypted_token):
    """Decrypt an encrypted token"""
    try:
        return fernet.decrypt(encrypted_token.encode()).decode()
    except:
        return encrypted_token  # Return as-is if decryption fails

def refresh_twitter_token(account_id, retry_count=0):
    """Refresh an expired Twitter OAuth 2.0 token
    
    Args:
        account_id: The database ID of the Twitter account
        retry_count: Current retry attempt (for exponential backoff)
    
    Returns:
        tuple: (success, new_access_token or error_message)
    """
    max_retries = 3
    if retry_count >= max_retries:
        return False, "Max refresh retries exceeded"
    
    conn = get_db()
    
    try:
        # Get account with refresh token
        account = conn.execute(
            'SELECT * FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return False, "Account not found"
        
        if not account['refresh_token']:
            conn.close()
            return False, "No refresh token available"
        
        # Decrypt refresh token
        refresh_token = decrypt_token(account['refresh_token'])
        
        # Prepare refresh request
        token_url = 'https://api.twitter.com/2/oauth2/token'
        
        auth_string = f"{TWITTER_CLIENT_ID}:{TWITTER_CLIENT_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'client_id': TWITTER_CLIENT_ID
        }
        
        # Add exponential backoff delay for retries
        if retry_count > 0:
            import time
            delay = (2 ** retry_count) + (secrets.randbelow(1000) / 1000)
            print(f"Retry {retry_count}/{max_retries} after {delay:.2f}s delay...")
            time.sleep(delay)
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            new_access_token = tokens['access_token']
            new_refresh_token = tokens.get('refresh_token', refresh_token)  # Sometimes a new refresh token is provided
            expires_in = tokens.get('expires_in', 7200)  # Default 2 hours
            
            # Encrypt new tokens
            encrypted_access_token = fernet.encrypt(new_access_token.encode()).decode()
            encrypted_refresh_token = fernet.encrypt(new_refresh_token.encode()).decode()
            
            # Calculate token expiry time (with 5 minute buffer)
            token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in - 300)
            
            # Update account with new tokens and reset failure count
            conn.execute('''
                UPDATE twitter_account 
                SET access_token = ?, 
                    refresh_token = ?, 
                    token_expires_at = ?,
                    last_token_refresh = ?,
                    refresh_failure_count = 0,
                    updated_at = ?
                WHERE id = ?
            ''', (
                encrypted_access_token, 
                encrypted_refresh_token, 
                token_expires_at.isoformat(),
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
                account_id
            ))
            
            conn.commit()
            conn.close()
            
            print(f"Successfully refreshed token for account {account['username']}")
            return True, new_access_token
            
        else:
            # Handle refresh failure
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
            error_msg = error_data.get('error_description', f'HTTP {response.status_code}')
            
            # If it's a rate limit error, retry with backoff
            if response.status_code == 429:
                conn.close()
                return refresh_twitter_token(account_id, retry_count + 1)
            
            # Update failure count
            conn.execute('''
                UPDATE twitter_account 
                SET refresh_failure_count = refresh_failure_count + 1,
                    updated_at = ?
                WHERE id = ?
            ''', (datetime.now(UTC).isoformat(), account_id))
            
            conn.commit()
            conn.close()
            
            print(f"Failed to refresh token for account {account_id}: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        if conn:
            conn.close()
        print(f"Exception during token refresh: {str(e)}")
        return False, str(e)

def post_to_twitter(account_id, tweet_text, reply_to_tweet_id=None, retry_after_refresh=True):
    """Post a tweet to Twitter using the account's credentials with automatic token refresh
    
    Args:
        account_id: The database ID of the Twitter account
        tweet_text: The text content of the tweet
        reply_to_tweet_id: Optional Twitter ID of the tweet to reply to (for threads)
        retry_after_refresh: Whether to retry after refreshing token (prevents infinite loops)
    """
    conn = get_db()
    
    # Get account credentials
    account = conn.execute(
        'SELECT * FROM twitter_account WHERE id = ?', 
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return False, "Account not found"
    
    # Check if mock mode
    if mock_mode_override['enabled']:
        conn.close()
        mock_tweet_id = f"mock_{datetime.now().timestamp()}"
        print(f"[MOCK MODE] Would post tweet for {account['username']}: {tweet_text}")
        return True, mock_tweet_id
    
    # Check rate limit before attempting to post
    can_post, wait_time = check_rate_limit(account_id)
    if not can_post:
        conn.close()
        return False, f"Rate limit approaching for account. Wait {wait_time:.0f} seconds."
    
    # Check if token needs proactive refresh (within 15 minutes of expiry)
    if account['token_expires_at']:
        token_expires = datetime.fromisoformat(account['token_expires_at'])
        # Make token_expires timezone-aware if it isn't already
        if token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=UTC)
        if datetime.now(UTC) >= token_expires - timedelta(minutes=15):
            print(f"Token for {account['username']} expires soon, refreshing proactively...")
            conn.close()
            success, result = refresh_twitter_token(account_id)
            if success:
                # Re-fetch account with new token
                conn = get_db()
                account = conn.execute(
                    'SELECT * FROM twitter_account WHERE id = ?', 
                    (account_id,)
                ).fetchone()
            else:
                print(f"Proactive refresh failed: {result}")
    
    try:
        # Decrypt tokens
        access_token = decrypt_token(account['access_token'])
        access_token_secret = decrypt_token(account['access_token_secret']) if account['access_token_secret'] else None
        
        print(f"Posting tweet for account: {account['username']}")
        print(f"OAuth type: {'OAuth 2.0' if not access_token_secret or not access_token_secret.strip() else 'OAuth 1.0a'}")
        
        # Check if OAuth 2.0 (no secret) or OAuth 1.0a (with secret)
        if access_token_secret and access_token_secret.strip():
            # OAuth 1.0a - use direct API call (tweepy has Python 3.13 issues)
            conn.close()
            return False, "OAuth 1.0a not supported. Please re-authorize with OAuth 2.0."
        else:
            # OAuth 2.0 - direct API call
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            data = {'text': tweet_text}
            
            # Add reply parameter if this is part of a thread
            if reply_to_tweet_id:
                data['reply'] = {
                    'in_reply_to_tweet_id': reply_to_tweet_id
                }
            
            response = requests.post(
                'https://api.twitter.com/2/tweets',
                headers=headers,
                json=data
            )
            
            if response.status_code == 401 and retry_after_refresh:
                # Token expired, try to refresh
                conn.close()
                print(f"Access token expired for {account['username']}, attempting refresh...")
                success, new_token = refresh_twitter_token(account_id)
                
                if success:
                    # Retry the post with refreshed token
                    print("Token refreshed successfully, retrying post...")
                    return post_to_twitter(account_id, tweet_text, reply_to_tweet_id, retry_after_refresh=False)
                else:
                    return False, f"Token refresh failed: {new_token}"
            
            if response.status_code == 429:
                # Rate limit hit - update our tracker
                conn.close()
                retry_after = response.headers.get('x-rate-limit-reset')
                if retry_after:
                    with rate_limit_tracker['lock']:
                        reset_time = int(retry_after)
                        rate_limit_tracker['accounts'][account_id]['reset_time'] = reset_time
                        rate_limit_tracker['accounts'][account_id]['count'] = 200  # Mark as maxed out
                    wait_time = reset_time - time.time()
                    error_msg = f"Rate limit hit. Reset in {wait_time:.0f} seconds"
                else:
                    error_msg = "Rate limit hit. Please wait before posting again."
                print(error_msg)
                return False, error_msg
            
            if response.status_code != 201:
                conn.close()
                error_msg = f"Twitter API error (status {response.status_code}): {response.text}"
                print(error_msg)
                return False, error_msg
            
            tweet_id = response.json()['data']['id']
        
        conn.close()
        print(f"Successfully posted tweet with ID: {tweet_id}")
        return True, tweet_id
        
    except Exception as e:
        conn.close()
        error_msg = f"Exception during posting: {str(e)}"
        print(error_msg)
        return False, error_msg

# WORKING ENDPOINTS

@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check - no auth required"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(UTC).isoformat(),
        'version': '2.0.0-simple'
    })

@app.route('/api/v1/test', methods=['GET'])
def test():
    """Test endpoint with API key"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    return jsonify({
        'status': 'success',
        'message': 'API key validated!'
    })

@app.route('/api/v1/accounts', methods=['GET'])
def get_accounts():
    """Get all Twitter accounts"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    account_type = request.args.get('type')
    
    try:
        conn = get_db()
        if account_type:
            cursor = conn.execute(
                'SELECT id, username, status, account_type, created_at FROM twitter_account WHERE account_type = ? ORDER BY created_at DESC',
                (account_type,)
            )
        else:
            cursor = conn.execute('SELECT id, username, status, account_type, created_at FROM twitter_account ORDER BY created_at DESC')
        accounts = cursor.fetchall()
        conn.close()
        
        result = []
        for acc in accounts:
            result.append({
                'id': acc['id'],
                'username': acc['username'],
                'status': acc['status'],
                'account_type': acc['account_type'] if 'account_type' in acc.keys() else 'managed',
                'created_at': acc['created_at']
            })
        
        return jsonify({
            'accounts': result,
            'total': len(result)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/<int:account_id>', methods=['GET'])
def get_account(account_id):
    """Get specific account"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        cursor = conn.execute('SELECT * FROM twitter_account WHERE id = ?', (account_id,))
        account = cursor.fetchone()
        conn.close()
        
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        return jsonify({
            'id': account['id'],
            'username': account['username'],
            'status': account['status'],
            'created_at': account['created_at']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Account Type Management
@app.route('/api/v1/accounts/<int:account_id>/set-type', methods=['POST'])
def set_account_type(account_id):
    """Set account type (managed or list_owner)"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data or 'account_type' not in data:
        return jsonify({'error': 'account_type is required'}), 400
    
    account_type = data['account_type']
    if account_type not in ['managed', 'list_owner']:
        return jsonify({'error': 'account_type must be "managed" or "list_owner"'}), 400
    
    try:
        conn = get_db()
        
        # Check if account exists
        account = conn.execute(
            'SELECT id, username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Update account type
        conn.execute(
            'UPDATE twitter_account SET account_type = ?, updated_at = ? WHERE id = ?',
            (account_type, datetime.now(UTC).isoformat(), account_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Account type updated to {account_type}',
            'account_id': account_id,
            'username': account['username'],
            'account_type': account_type
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweet', methods=['POST'])
def create_tweet():
    """Create a new tweet"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data or 'text' not in data or 'account_id' not in data:
        return jsonify({'error': 'Missing text or account_id'}), 400
    
    try:
        conn = get_db()
        cursor = conn.execute(
            'INSERT INTO tweet (twitter_account_id, content, status, created_at) VALUES (?, ?, ?, ?)',
            (data['account_id'], data['text'], 'pending', datetime.now(UTC).isoformat())
        )
        tweet_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Tweet created successfully',
            'tweet_id': tweet_id
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/thread', methods=['POST'])
def create_thread():
    """Create a Twitter thread (multiple connected tweets)"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        tweets = data.get('tweets', [])
        thread_id = data.get('thread_id', str(uuid.uuid4()))
        
        if not account_id or not tweets:
            return jsonify({'error': 'account_id and tweets array are required'}), 400
        
        if len(tweets) < 2:
            return jsonify({'error': 'A thread must contain at least 2 tweets'}), 400
        
        conn = get_db()
        
        # Verify account exists
        account = conn.execute(
            'SELECT * FROM twitter_account WHERE id = ?', 
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Create all tweets in the thread as pending
        created_tweets = []
        for i, tweet_text in enumerate(tweets):
            cursor = conn.execute(
                '''INSERT INTO tweet (twitter_account_id, content, thread_id, thread_position, status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (account_id, tweet_text, thread_id, i, 'pending')
            )
            tweet_id = cursor.lastrowid
            created_tweets.append({
                'id': tweet_id,
                'position': i,
                'content': tweet_text
            })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Thread created with {len(tweets)} tweets',
            'thread_id': thread_id,
            'tweets': created_tweets
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/thread/post/<thread_id>', methods=['POST'])
def post_thread(thread_id):
    """Post all tweets in a thread to Twitter"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # First check if thread exists at all
        thread_check = conn.execute(
            '''SELECT COUNT(*) as total,
                      SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                      SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted,
                      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
               FROM tweet 
               WHERE thread_id = ?''',
            (thread_id,)
        ).fetchone()
        
        if thread_check['total'] == 0:
            conn.close()
            return jsonify({'error': f'Thread {thread_id} not found'}), 404
        
        if thread_check['posted'] > 0:
            conn.close()
            return jsonify({
                'error': 'Thread already posted',
                'stats': {
                    'total': thread_check['total'],
                    'posted': thread_check['posted'],
                    'pending': thread_check['pending'],
                    'failed': thread_check['failed']
                }
            }), 400
        
        # Get all tweets in the thread ordered by position
        tweets = conn.execute(
            '''SELECT id, twitter_account_id, content, thread_position 
               FROM tweet 
               WHERE thread_id = ? AND status = 'pending'
               ORDER BY thread_position''',
            (thread_id,)
        ).fetchall()
        
        if not tweets:
            conn.close()
            return jsonify({
                'error': 'No pending tweets found in thread',
                'stats': {
                    'total': thread_check['total'],
                    'posted': thread_check['posted'],
                    'pending': thread_check['pending'],
                    'failed': thread_check['failed']
                }
            }), 404
        
        # Post tweets sequentially, each replying to the previous
        posted_tweets = []
        previous_tweet_id = None
        
        for tweet in tweets:
            success, result = post_to_twitter(
                tweet['twitter_account_id'], 
                tweet['content'],
                reply_to_tweet_id=previous_tweet_id
            )
            
            if success:
                # Update tweet status and twitter_id
                conn.execute(
                    '''UPDATE tweet 
                       SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                       WHERE id = ?''',
                    ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                )
                conn.commit()
                
                posted_tweets.append({
                    'tweet_id': tweet['id'],
                    'twitter_id': result,
                    'position': tweet['thread_position'],
                    'status': 'posted'
                })
                
                # Set this tweet as the one to reply to for the next tweet
                previous_tweet_id = result
            else:
                # If posting fails, stop the thread
                conn.execute(
                    'UPDATE tweet SET status = ? WHERE id = ?',
                    ('failed', tweet['id'])
                )
                conn.commit()
                
                posted_tweets.append({
                    'tweet_id': tweet['id'],
                    'position': tweet['thread_position'],
                    'status': 'failed',
                    'error': result
                })
                break
        
        conn.close()
        
        return jsonify({
            'message': f'Thread posting completed',
            'thread_id': thread_id,
            'posted': len([t for t in posted_tweets if t['status'] == 'posted']),
            'failed': len([t for t in posted_tweets if t['status'] == 'failed']),
            'tweets': posted_tweets
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/threads', methods=['GET'])
def get_threads():
    """Get all threads"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get unique threads with their tweet count
        threads = conn.execute('''
            SELECT 
                thread_id,
                twitter_account_id,
                COUNT(*) as tweet_count,
                MIN(created_at) as created_at,
                SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted_count,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM tweet
            WHERE thread_id IS NOT NULL
            GROUP BY thread_id, twitter_account_id
            ORDER BY created_at DESC
        ''').fetchall()
        
        result = []
        for thread in threads:
            # Get account info
            account = conn.execute(
                'SELECT username FROM twitter_account WHERE id = ?',
                (thread['twitter_account_id'],)
            ).fetchone()
            
            result.append({
                'thread_id': thread['thread_id'],
                'account_id': thread['twitter_account_id'],
                'account_username': account['username'] if account else 'Unknown',
                'tweet_count': thread['tweet_count'],
                'posted_count': thread['posted_count'],
                'pending_count': thread['pending_count'],
                'failed_count': thread['failed_count'],
                'created_at': thread['created_at']
            })
        
        conn.close()
        return jsonify({'threads': result})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/thread/<thread_id>', methods=['GET'])
def get_thread(thread_id):
    """Get details of a specific thread"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get all tweets in the thread
        tweets = conn.execute('''
            SELECT 
                t.id,
                t.content,
                t.status,
                t.twitter_id,
                t.reply_to_tweet_id,
                t.thread_position,
                t.created_at,
                t.posted_at,
                a.username
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.thread_id = ?
            ORDER BY t.thread_position
        ''', (thread_id,)).fetchall()
        
        if not tweets:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        result = {
            'thread_id': thread_id,
            'account_username': tweets[0]['username'],
            'tweet_count': len(tweets),
            'tweets': []
        }
        
        for tweet in tweets:
            result['tweets'].append({
                'id': tweet['id'],
                'content': tweet['content'],
                'status': tweet['status'],
                'twitter_id': tweet['twitter_id'],
                'reply_to_tweet_id': tweet['reply_to_tweet_id'],
                'position': tweet['thread_position'],
                'created_at': tweet['created_at'],
                'posted_at': tweet['posted_at']
            })
        
        conn.close()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/thread/<thread_id>/debug', methods=['GET'])
def debug_thread(thread_id):
    """Debug endpoint to check thread status"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get all tweets in the thread
        tweets = conn.execute('''
            SELECT id, content, status, thread_position, created_at
            FROM tweet 
            WHERE thread_id = ?
            ORDER BY thread_position
        ''', (thread_id,)).fetchall()
        
        if not tweets:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        result = {
            'thread_id': thread_id,
            'tweet_count': len(tweets),
            'tweets': []
        }
        
        for tweet in tweets:
            result['tweets'].append({
                'id': tweet['id'],
                'content': tweet['content'][:50] + '...' if len(tweet['content']) > 50 else tweet['content'],
                'status': tweet['status'],
                'position': tweet['thread_position'],
                'created_at': tweet['created_at']
            })
        
        conn.close()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets', methods=['GET'])
def get_tweets():
    """Get all tweets"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        cursor = conn.execute('''
            SELECT t.id, t.content as text, t.status, t.created_at, a.username 
            FROM tweet t 
            JOIN twitter_account a ON t.twitter_account_id = a.id 
            ORDER BY t.created_at DESC 
            LIMIT 50
        ''')
        tweets = cursor.fetchall()
        conn.close()
        
        result = []
        for tweet in tweets:
            result.append({
                'id': tweet['id'],
                'text': tweet['text'],
                'status': tweet['status'],
                'created_at': tweet['created_at'],
                'username': tweet['username']
            })
        
        return jsonify({
            'tweets': result,
            'total': len(result)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/pending-analysis', methods=['GET'])
def analyze_pending_tweets():
    """Analyze pending tweets to understand why old tweets are still pending"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get all pending tweets with account info
        pending_tweets = conn.execute('''
            SELECT t.id, t.content, t.status, t.created_at, t.twitter_account_id,
                   a.username, a.status as account_status
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.status = 'pending'
            ORDER BY t.id
        ''').fetchall()
        
        # Group by ID ranges
        id_ranges = {
            'very_old': [],  # < 100
            'old': [],       # 100-500
            'recent': [],    # > 500
            'no_account': [] # Account doesn't exist
        }
        
        for tweet in pending_tweets:
            tweet_info = {
                'id': tweet['id'],
                'content_preview': tweet['content'][:50] + '...' if len(tweet['content']) > 50 else tweet['content'],
                'created_at': tweet['created_at'],
                'account_id': tweet['twitter_account_id'],
                'username': tweet['username'],
                'account_status': tweet['account_status']
            }
            
            if tweet['username'] is None:
                id_ranges['no_account'].append(tweet_info)
            elif tweet['id'] < 100:
                id_ranges['very_old'].append(tweet_info)
            elif tweet['id'] < 500:
                id_ranges['old'].append(tweet_info)
            else:
                id_ranges['recent'].append(tweet_info)
        
        # Get summary stats
        summary = {
            'total_pending': len(pending_tweets),
            'very_old_count': len(id_ranges['very_old']),
            'old_count': len(id_ranges['old']),
            'recent_count': len(id_ranges['recent']),
            'orphaned_count': len(id_ranges['no_account'])
        }
        
        # Get account distribution
        account_dist = conn.execute('''
            SELECT a.username, COUNT(t.id) as pending_count
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.status = 'pending'
            GROUP BY t.twitter_account_id
            ORDER BY pending_count DESC
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'summary': summary,
            'id_ranges': id_ranges,
            'account_distribution': [dict(row) for row in account_dist],
            'recommendation': 'Consider cleaning up old pending tweets with IDs < 500 that may be from deleted accounts'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/auth/twitter', methods=['GET'])
def twitter_auth():
    """Get Twitter OAuth URL"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    import secrets
    import base64
    import urllib.parse
    
    # Generate PKCE parameters
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store code_verifier and state (in production, use Redis or database)
    conn = get_db()
    conn.execute(
        'INSERT INTO oauth_state (state, code_verifier, created_at) VALUES (?, ?, ?)',
        (state, code_verifier, datetime.now(UTC).isoformat())
    )
    conn.commit()
    conn.close()
    
    # Build OAuth URL
    params = {
        'response_type': 'code',
        'client_id': TWITTER_CLIENT_ID,
        'redirect_uri': TWITTER_CALLBACK_URL,
        'scope': 'tweet.read tweet.write users.read list.read list.write offline.access',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    
    auth_url = f"https://twitter.com/i/oauth2/authorize?{urllib.parse.urlencode(params)}"
    
    return jsonify({
        'auth_url': auth_url,
        'state': state
    })

@app.route('/api/v1/auth/callback', methods=['GET', 'POST'])
def auth_callback():
    """Handle OAuth callback from Twitter (API endpoint version)"""
    # For API endpoint, require API key
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    # Get parameters from request
    if request.method == 'GET':
        code = request.args.get('code')
        state = request.args.get('state')
    else:
        data = request.get_json()
        code = data.get('code')
        state = data.get('state')
    
    if not code or not state:
        return jsonify({'error': 'Missing code or state'}), 400
    
    # Retrieve code_verifier from database
    conn = get_db()
    oauth_data = conn.execute(
        'SELECT code_verifier FROM oauth_state WHERE state = ?',
        (state,)
    ).fetchone()
    
    if not oauth_data:
        conn.close()
        return jsonify({'error': 'Invalid state'}), 400
    
    code_verifier = oauth_data['code_verifier']
    
    # Exchange code for tokens
    token_url = 'https://api.twitter.com/2/oauth2/token'
    
    auth_string = f"{TWITTER_CLIENT_ID}:{TWITTER_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'client_id': TWITTER_CLIENT_ID,
        'redirect_uri': TWITTER_CALLBACK_URL,
        'code_verifier': code_verifier
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code != 200:
        conn.close()
        return jsonify({
            'error': 'Failed to exchange code for tokens',
            'details': response.json()
        }), 400
    
    tokens = response.json()
    access_token = tokens['access_token']
    refresh_token = tokens.get('refresh_token')
    expires_in = tokens.get('expires_in', 7200)  # Default 2 hours
    
    # Get user info
    user_response = requests.get(
        'https://api.twitter.com/2/users/me',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if user_response.status_code != 200:
        conn.close()
        return jsonify({'error': 'Failed to get user info'}), 400
    
    user_data = user_response.json()['data']
    username = user_data['username']
    
    # Encrypt tokens
    encrypted_access_token = fernet.encrypt(access_token.encode()).decode()
    encrypted_refresh_token = fernet.encrypt(refresh_token.encode()).decode() if refresh_token else None
    
    # Calculate token expiry time (store actual expiry, no buffer)
    token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    
    # Check if account exists
    existing = conn.execute(
        'SELECT id FROM twitter_account WHERE username = ?',
        (username,)
    ).fetchone()
    
    if existing:
        # Update existing account with token metadata
        conn.execute('''
            UPDATE twitter_account 
            SET access_token = ?, 
                refresh_token = ?, 
                status = ?, 
                token_expires_at = ?,
                last_token_refresh = ?,
                refresh_failure_count = 0,
                updated_at = ? 
            WHERE username = ?
        ''', (
            encrypted_access_token, 
            encrypted_refresh_token, 
            'active', 
            token_expires_at.isoformat(),
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat(), 
            username
        ))
        account_id = existing['id']
    else:
        # Create new account with token metadata
        cursor = conn.execute('''
            INSERT INTO twitter_account 
            (username, access_token, access_token_secret, refresh_token, status, 
             token_expires_at, last_token_refresh, refresh_failure_count, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username, 
            encrypted_access_token, 
            None, 
            encrypted_refresh_token, 
            'active',
            token_expires_at.isoformat(),
            datetime.now(UTC).isoformat(),
            0,
            datetime.now(UTC).isoformat()
        ))
        account_id = cursor.lastrowid
    
    # Clean up oauth_state
    conn.execute('DELETE FROM oauth_state WHERE state = ?', (state,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': 'Authorization successful',
        'account_id': account_id,
        'username': username
    })

@app.route('/api/v1/mock-mode', methods=['GET', 'POST'])
def mock_mode():
    """Get or set mock mode"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    if request.method == 'POST':
        data = request.get_json()
        if data and 'enabled' in data:
            mock_mode_override['enabled'] = data['enabled']
            return jsonify({
                'message': f"Mock mode {'enabled' if mock_mode_override['enabled'] else 'disabled'}",
                'mock_mode': mock_mode_override['enabled']
            })
    
    return jsonify({'mock_mode': mock_mode_override['enabled']})

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get counts
        accounts_count = conn.execute('SELECT COUNT(*) FROM twitter_account').fetchone()[0]
        tweets_count = conn.execute('SELECT COUNT(*) FROM tweet').fetchone()[0]
        pending_count = conn.execute('SELECT COUNT(*) FROM tweet WHERE status = "pending"').fetchone()[0]
        posted_count = conn.execute('SELECT COUNT(*) FROM tweet WHERE status = "posted"').fetchone()[0]
        failed_count = conn.execute('SELECT COUNT(*) FROM tweet WHERE status = "failed"').fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'accounts': {
                'total': accounts_count,
                'active': accounts_count  # Simplified
            },
            'tweets': {
                'total': tweets_count,
                'pending': pending_count,
                'posted': posted_count,
                'failed': failed_count
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/user-activity-rankings', methods=['GET'])
def get_user_activity_rankings():
    """Get top 10 users ranked by number of tweets and threads"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get top 10 users by total activity (tweets + threads)
        rankings = conn.execute('''
            WITH user_activity AS (
                SELECT 
                    a.id,
                    a.username,
                    COUNT(DISTINCT t.id) as tweet_count,
                    SUM(CASE WHEN t.status = 'posted' THEN 1 ELSE 0 END) as posted_count,
                    SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    COUNT(DISTINCT th.id) as thread_count
                FROM twitter_account a
                LEFT JOIN tweet t ON a.id = t.twitter_account_id
                LEFT JOIN thread th ON a.username = th.account_username
                GROUP BY a.id, a.username
                HAVING (tweet_count > 0 OR thread_count > 0)
            )
            SELECT * FROM user_activity
            ORDER BY (tweet_count + thread_count) DESC
            LIMIT 10
        ''').fetchall()
        
        result = []
        for rank, user in enumerate(rankings, 1):
            result.append({
                'rank': rank,
                'id': user['id'],
                'username': user['username'],
                'displayName': user['username'],  # Use username as display name
                'profilePicture': None,  # No profile picture in database
                'tweetCount': user['tweet_count'],
                'threadCount': user['thread_count'],
                'totalActivity': user['tweet_count'] + user['thread_count'],
                'postedCount': user['posted_count'],
                'pendingCount': user['pending_count'],
                'failedCount': user['failed_count']
            })
        
        conn.close()
        
        return jsonify({
            'rankings': result,
            'timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/token-health', methods=['GET'])
def check_token_health():
    """Check health status of all account tokens"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get all accounts with token info
        accounts = conn.execute('''
            SELECT id, username, status, token_expires_at, last_token_refresh, 
                   refresh_failure_count, updated_at
            FROM twitter_account
            ORDER BY username
        ''').fetchall()
        
        current_time = datetime.now(UTC)
        health_report = {
            'healthy': [],
            'expiring_soon': [],
            'expired': [],
            'refresh_failures': [],
            'no_refresh_token': []
        }
        
        for account in accounts:
            account_info = {
                'id': account['id'],
                'username': account['username'],
                'status': account['status'],
                'last_refresh': account['last_token_refresh'],
                'failure_count': account['refresh_failure_count'] or 0
            }
            
            # Check if account has refresh issues
            if account['refresh_failure_count'] and account['refresh_failure_count'] > 0:
                account_info['health_status'] = 'refresh_failures'
                health_report['refresh_failures'].append(account_info)
                continue
            
            # Check token expiry
            if account['token_expires_at']:
                expires_at = datetime.fromisoformat(account['token_expires_at'])
                # Make expires_at timezone-aware if it isn't already
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                time_until_expiry = expires_at - current_time
                account_info['expires_at'] = account['token_expires_at']
                account_info['time_until_expiry'] = str(time_until_expiry)
                
                if time_until_expiry < timedelta(minutes=0):
                    account_info['health_status'] = 'expired'
                    health_report['expired'].append(account_info)
                elif time_until_expiry < timedelta(hours=1):
                    account_info['health_status'] = 'expiring_soon'
                    health_report['expiring_soon'].append(account_info)
                else:
                    account_info['health_status'] = 'healthy'
                    health_report['healthy'].append(account_info)
            else:
                # No expiry info, check if it's an old OAuth 1.0 account
                account_info['health_status'] = 'no_refresh_token'
                health_report['no_refresh_token'].append(account_info)
        
        conn.close()
        
        summary = {
            'total_accounts': len(accounts),
            'healthy': len(health_report['healthy']),
            'expiring_soon': len(health_report['expiring_soon']),
            'expired': len(health_report['expired']),
            'refresh_failures': len(health_report['refresh_failures']),
            'no_refresh_token': len(health_report['no_refresh_token'])
        }
        
        return jsonify({
            'summary': summary,
            'details': health_report,
            'timestamp': current_time.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/<int:account_id>/refresh-token', methods=['POST'])
def manual_refresh_token(account_id):
    """Manually refresh token for a specific account"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        success, result = refresh_twitter_token(account_id)
        
        if success:
            return jsonify({
                'message': 'Token refreshed successfully',
                'account_id': account_id
            })
        else:
            return jsonify({
                'error': 'Token refresh failed',
                'reason': result
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/refresh-tokens', methods=['POST'])
def refresh_all_expiring_tokens():
    """Refresh tokens for all accounts that are expired or expiring soon"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get accounts with tokens expiring in the next hour
        current_time = datetime.now(UTC)
        threshold_time = current_time + timedelta(hours=1)
        
        accounts = conn.execute('''
            SELECT id, username, token_expires_at, refresh_failure_count
            FROM twitter_account
            WHERE token_expires_at IS NOT NULL 
            AND token_expires_at < ?
            AND refresh_failure_count < 3
            ORDER BY token_expires_at
        ''', (threshold_time.isoformat(),)).fetchall()
        
        results = {
            'total': len(accounts),
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        for account in accounts:
            account_detail = {
                'id': account['id'],
                'username': account['username'],
                'token_expires_at': account['token_expires_at']
            }
            
            success, message = refresh_twitter_token(account['id'])
            
            if success:
                results['success'] += 1
                account_detail['status'] = 'refreshed'
            else:
                results['failed'] += 1
                account_detail['status'] = 'failed'
                account_detail['error'] = message
            
            results['details'].append(account_detail)
        
        conn.close()
        
        return jsonify({
            'message': f"Processed {results['total']} accounts",
            'results': results,
            'timestamp': current_time.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/<int:account_id>/clear-failures', methods=['POST'])
def clear_refresh_failures(account_id):
    """Clear refresh failure count for an account (useful after manual intervention)"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check if account exists
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Clear failure count
        conn.execute('''
            UPDATE twitter_account 
            SET refresh_failure_count = 0,
                updated_at = ?
            WHERE id = ?
        ''', (datetime.now(UTC).isoformat(), account_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Failure count cleared',
            'account_id': account_id,
            'username': account['username']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweet/post/<int:tweet_id>', methods=['POST'])
def post_tweet(tweet_id):
    """Post a specific pending tweet to Twitter"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get the tweet
        tweet = conn.execute(
            'SELECT * FROM tweet WHERE id = ? AND status = "pending"',
            (tweet_id,)
        ).fetchone()
        
        if not tweet:
            conn.close()
            return jsonify({'error': 'Tweet not found or already posted'}), 404
        
        # Post to Twitter
        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
        
        if success:
            # Update tweet status to posted
            conn.execute(
                'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                ('posted', result, datetime.now(UTC).isoformat(), tweet_id)
            )
            conn.commit()
            conn.close()
            
            return jsonify({
                'message': 'Tweet posted successfully',
                'tweet_id': tweet_id,
                'twitter_tweet_id': result
            })
        else:
            # Update tweet status to failed
            conn.execute(
                'UPDATE tweet SET status = ? WHERE id = ?',
                ('failed', tweet_id)
            )
            conn.commit()
            conn.close()
            
            return jsonify({
                'error': 'Failed to post tweet',
                'reason': result
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/post-pending', methods=['POST'])
def post_pending_tweets():
    """Post all pending tweets with batch processing to prevent timeouts"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        # Get batch size from request or use default
        data = request.get_json() or {}
        batch_size = min(data.get('batch_size', 10), 50)  # Max 50 tweets per batch
        offset = data.get('offset', 0)
        
        conn = get_db()
        
        # Get total count of pending tweets
        total_count = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE status = "pending"'
        ).fetchone()['count']
        
        # Get batch of pending tweets
        pending_tweets = conn.execute(
            'SELECT * FROM tweet WHERE status = "pending" ORDER BY created_at LIMIT ? OFFSET ?',
            (batch_size, offset)
        ).fetchall()
        
        results = {
            'total_pending': total_count,
            'batch_size': batch_size,
            'offset': offset,
            'processed': len(pending_tweets),
            'posted': 0,
            'failed': 0,
            'details': [],
            'has_more': (offset + len(pending_tweets)) < total_count
        }
        
        for i, tweet in enumerate(pending_tweets):
            try:
                # Add delay between tweets (except for the first one)
                if i > 0:
                    delay = get_rate_limit_delay(tweet['twitter_account_id'])
                    time.sleep(delay)
                
                success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
                
                if success:
                    # Update to posted with retry logic
                    retry_count = 0
                    while retry_count < 3:
                        try:
                            conn.execute(
                                'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                                ('posted', result, datetime.now(UTC).isoformat(), tweet['id'])
                            )
                            conn.commit()
                            break
                        except sqlite3.OperationalError as e:
                            if "database is locked" in str(e) and retry_count < 2:
                                retry_count += 1
                                time.sleep(0.5 * retry_count)  # Exponential backoff
                                continue
                            raise
                    
                    results['posted'] += 1
                    results['details'].append({
                        'tweet_id': tweet['id'],
                        'status': 'posted',
                        'twitter_tweet_id': result
                    })
                else:
                    # Update to failed with retry logic
                    retry_count = 0
                    while retry_count < 3:
                        try:
                            conn.execute(
                                'UPDATE tweet SET status = ? WHERE id = ?',
                                ('failed', tweet['id'])
                            )
                            conn.commit()
                            break
                        except sqlite3.OperationalError as e:
                            if "database is locked" in str(e) and retry_count < 2:
                                retry_count += 1
                                time.sleep(0.5 * retry_count)
                                continue
                            raise
                    
                    results['failed'] += 1
                    results['details'].append({
                        'tweet_id': tweet['id'],
                        'status': 'failed',
                        'error': result
                    })
            except Exception as e:
                # If any error occurs, mark as failed
                results['failed'] += 1
                results['details'].append({
                    'tweet_id': tweet['id'],
                    'status': 'failed',
                    'error': f'Processing error: {str(e)}'
                })
        
        conn.close()
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Background job tracking
background_jobs = {}

def post_tweets_background(job_id, batch_size=10):
    """Background worker to post pending tweets"""
    conn = None
    try:
        background_jobs[job_id]['status'] = 'running'
        background_jobs[job_id]['started_at'] = datetime.now(UTC).isoformat()
        
        total_posted = 0
        total_failed = 0
        offset = 0
        
        while True:
            try:
                conn = get_db()
                
                # Get batch of pending tweets
                pending_tweets = conn.execute(
                    'SELECT * FROM tweet WHERE status = "pending" ORDER BY created_at LIMIT ? OFFSET ?',
                    (batch_size, offset)
                ).fetchall()
                
                if not pending_tweets:
                    break
                
                for j, tweet in enumerate(pending_tweets):
                    try:
                        # Add delay between tweets
                        if j > 0 or offset > 0:  # Delay unless it's the very first tweet
                            delay = get_rate_limit_delay(tweet['twitter_account_id'])
                            time.sleep(delay)
                        
                        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
                        
                        # Retry logic for database updates
                        retry_count = 0
                        while retry_count < 3:
                            try:
                                if success:
                                    conn.execute(
                                        'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                                        ('posted', result, datetime.now(UTC).isoformat(), tweet['id'])
                                    )
                                    total_posted += 1
                                else:
                                    conn.execute(
                                        'UPDATE tweet SET status = ? WHERE id = ?',
                                        ('failed', tweet['id'])
                                    )
                                    total_failed += 1
                                conn.commit()
                                break
                            except sqlite3.OperationalError as e:
                                if "database is locked" in str(e) and retry_count < 2:
                                    retry_count += 1
                                    time.sleep(0.5 * retry_count)
                                    continue
                                raise
                        
                        # Update job progress
                        background_jobs[job_id]['posted'] = total_posted
                        background_jobs[job_id]['failed'] = total_failed
                        background_jobs[job_id]['processed'] = total_posted + total_failed
                        
                    except Exception as e:
                        print(f"Error processing tweet {tweet['id']}: {e}")
                        total_failed += 1
                        background_jobs[job_id]['failed'] = total_failed
                        background_jobs[job_id]['processed'] = total_posted + total_failed
                
                conn.close()
                conn = None
                
                offset += batch_size
                
            except sqlite3.OperationalError as e:
                if conn:
                    conn.close()
                    conn = None
                if "database is locked" in str(e):
                    print(f"Database locked, retrying in 2 seconds...")
                    time.sleep(2)
                    continue
                raise
        
        background_jobs[job_id]['status'] = 'completed'
        background_jobs[job_id]['completed_at'] = datetime.now(UTC).isoformat()
        
    except Exception as e:
        background_jobs[job_id]['status'] = 'failed'
        background_jobs[job_id]['error'] = str(e)
        background_jobs[job_id]['completed_at'] = datetime.now(UTC).isoformat()
    finally:
        if conn:
            conn.close()

@app.route('/api/v1/tweets/post-pending-async', methods=['POST'])
def post_pending_tweets_async():
    """Post all pending tweets asynchronously in background"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        data = request.get_json() or {}
        batch_size = min(data.get('batch_size', 10), 50)
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Get total pending count
        conn = get_db()
        total_count = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE status = "pending"'
        ).fetchone()['count']
        conn.close()
        
        # Initialize job tracking
        background_jobs[job_id] = {
            'id': job_id,
            'status': 'pending',
            'total_pending': total_count,
            'posted': 0,
            'failed': 0,
            'processed': 0,
            'batch_size': batch_size,
            'created_at': datetime.now(UTC).isoformat()
        }
        
        # Start background thread
        thread = threading.Thread(
            target=post_tweets_background,
            args=(job_id, batch_size),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'started',
            'total_pending': total_count,
            'message': 'Background job started. Use /api/v1/jobs/{job_id} to check status.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a background job"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    if job_id not in background_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(background_jobs[job_id])

# Tweet Retry Endpoints
@app.route('/api/v1/tweet/retry/<int:tweet_id>', methods=['POST'])
def retry_failed_tweet(tweet_id):
    """Retry posting a specific failed tweet"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get the failed tweet
        tweet = conn.execute(
            'SELECT * FROM tweet WHERE id = ? AND status = "failed"',
            (tweet_id,)
        ).fetchone()
        
        if not tweet:
            conn.close()
            return jsonify({'error': 'Tweet not found or not in failed status'}), 404
        
        # Try to post to Twitter
        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
        
        if success:
            # Update tweet status to posted
            conn.execute(
                'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                ('posted', result, datetime.now(UTC).isoformat(), tweet_id)
            )
            conn.commit()
            conn.close()
            
            return jsonify({
                'message': 'Tweet posted successfully on retry',
                'tweet_id': tweet_id,
                'twitter_id': result
            })
        else:
            # Keep as failed (no updated_at column to update)
            conn.commit()
            conn.close()
            
            return jsonify({
                'error': 'Tweet retry failed',
                'reason': result,
                'tweet_id': tweet_id
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/retry-failed', methods=['POST'])
def retry_all_failed_tweets():
    """Retry all failed tweets or a batch of them"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        data = request.get_json() or {}
        batch_size = min(data.get('batch_size', 10), 50)
        offset = data.get('offset', 0)
        account_id = data.get('account_id')  # Optional: retry only for specific account
        
        conn = get_db()
        
        # Build query
        query = 'SELECT * FROM tweet WHERE status = "failed"'
        params = []
        
        if account_id:
            query += ' AND twitter_account_id = ?'
            params.append(account_id)
            
        query += ' ORDER BY created_at LIMIT ? OFFSET ?'
        params.extend([batch_size, offset])
        
        # Get failed tweets
        failed_tweets = conn.execute(query, params).fetchall()
        
        # Get total count
        count_query = 'SELECT COUNT(*) as count FROM tweet WHERE status = "failed"'
        count_params = []
        if account_id:
            count_query += ' AND twitter_account_id = ?'
            count_params.append(account_id)
        total_count = conn.execute(count_query, count_params).fetchone()['count']
        
        results = {
            'total_failed': total_count,
            'batch_size': batch_size,
            'offset': offset,
            'processed': len(failed_tweets),
            'posted': 0,
            'still_failed': 0,
            'details': [],
            'has_more': (offset + len(failed_tweets)) < total_count
        }
        
        for i, tweet in enumerate(failed_tweets):
            try:
                # Add delay between tweets
                if i > 0:
                    delay = get_rate_limit_delay(tweet['twitter_account_id'])
                    time.sleep(delay)
                
                success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
                
                if success:
                    # Update to posted
                    conn.execute(
                        'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                        ('posted', result, datetime.now(UTC).isoformat(), tweet['id'])
                    )
                    conn.commit()
                    
                    results['posted'] += 1
                    results['details'].append({
                        'tweet_id': tweet['id'],
                        'status': 'posted',
                        'twitter_tweet_id': result
                    })
                else:
                    # Keep as failed (no updated_at column to update)
                    conn.commit()
                    
                    results['still_failed'] += 1
                    results['details'].append({
                        'tweet_id': tweet['id'],
                        'status': 'failed',
                        'error': result
                    })
                    
            except Exception as e:
                results['still_failed'] += 1
                results['details'].append({
                    'tweet_id': tweet['id'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        conn.close()
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/reset-failed', methods=['POST'])
def reset_failed_tweets():
    """Reset failed tweets back to pending status"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        data = request.get_json() or {}
        tweet_ids = data.get('tweet_ids', [])  # Specific tweets to reset
        account_id = data.get('account_id')  # Reset all failed for this account
        days_old = data.get('days_old')  # Reset failed tweets older than X days
        
        if not tweet_ids and not account_id and days_old is None:
            return jsonify({'error': 'Provide tweet_ids, account_id, or days_old parameter'}), 400
        
        conn = get_db()
        
        # Build update query
        query = 'UPDATE tweet SET status = "pending" WHERE status = "failed"'
        params = []
        
        if tweet_ids:
            placeholders = ','.join('?' * len(tweet_ids))
            query += f' AND id IN ({placeholders})'
            params.extend(tweet_ids)
        
        if account_id:
            query += ' AND twitter_account_id = ?'
            params.append(account_id)
            
        if days_old is not None:
            cutoff_date = (datetime.now(UTC) - timedelta(days=days_old)).isoformat()
            query += ' AND created_at < ?'
            params.append(cutoff_date)
        
        # Get count before update
        count_query = query.replace('UPDATE tweet SET status = "pending"', 'SELECT COUNT(*) FROM tweet')
        count = conn.execute(count_query, params).fetchone()[0]
        
        # Execute update
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Reset {count} failed tweets to pending status',
            'count': count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/rate-limits', methods=['GET'])
def get_rate_limits():
    """Get current rate limit status for all accounts"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        accounts = conn.execute('SELECT id, username FROM twitter_account').fetchall()
        conn.close()
        
        current_time = time.time()
        rate_limit_info = []
        
        with rate_limit_tracker['lock']:
            for account in accounts:
                account_id = account['id']
                limits = rate_limit_tracker['accounts'][account_id]
                
                # Calculate remaining tweets and time until reset
                remaining = max(0, 180 - limits['count'])
                reset_in = max(0, limits['reset_time'] - current_time)
                tweets_posted = limits['count']
                
                # Calculate delay based on usage
                if tweets_posted < 50:
                    current_delay = 1
                elif tweets_posted < 100:
                    current_delay = 2
                elif tweets_posted < 150:
                    current_delay = 3
                else:
                    current_delay = 5
                
                rate_limit_info.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'tweets_posted': tweets_posted,
                    'tweets_remaining': remaining,
                    'reset_in_seconds': int(reset_in),
                    'reset_at': datetime.fromtimestamp(limits['reset_time']).isoformat() if limits['reset_time'] > 0 else None,
                    'current_delay': current_delay
                })
        
        return jsonify({
            'rate_limits': rate_limit_info,
            'timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/check-twitter-status', methods=['GET'])
def check_all_accounts_twitter_status():
    """Check Twitter status (suspended/locked/active) for all accounts"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        accounts = conn.execute('''
            SELECT id, username, access_token, token_expires_at 
            FROM twitter_account 
            WHERE status = 'active'
        ''').fetchall()
        conn.close()
        
        results = []
        
        for account in accounts:
            account_info = {
                'id': account['id'],
                'username': account['username'],
                'twitter_status': 'unknown',
                'error': None,
                'checked_at': datetime.now(UTC).isoformat()
            }
            
            try:
                # Decrypt access token
                access_token = decrypt_token(account['access_token'])
                
                # Check if token is expired
                if account['token_expires_at']:
                    token_expires = datetime.fromisoformat(account['token_expires_at'])
                    if token_expires < datetime.now(UTC):
                        account_info['twitter_status'] = 'token_expired'
                        account_info['error'] = 'OAuth token expired'
                        results.append(account_info)
                        continue
                
                # Call Twitter API to check account status
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                # Get user info by username
                response = requests.get(
                    f'https://api.twitter.com/2/users/by/username/{account["username"]}',
                    headers=headers,
                    params={
                        'user.fields': 'created_at,description,protected,public_metrics,verified,withheld'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get('data', {})
                    
                    # Check various status indicators
                    if user_data.get('withheld'):
                        account_info['twitter_status'] = 'withheld'
                        account_info['withheld_info'] = user_data['withheld']
                    elif user_data.get('protected'):
                        account_info['twitter_status'] = 'protected'
                    else:
                        account_info['twitter_status'] = 'active'
                        account_info['metrics'] = user_data.get('public_metrics', {})
                
                elif response.status_code == 401:
                    account_info['twitter_status'] = 'unauthorized'
                    account_info['error'] = 'Invalid or expired token'
                
                elif response.status_code == 403:
                    # Parse error details
                    error_data = response.json()
                    errors = error_data.get('errors', [])
                    
                    if errors:
                        error_detail = str(errors[0].get('detail', '')).lower()
                        error_title = str(errors[0].get('title', '')).lower()
                        
                        if 'suspended' in error_detail:
                            account_info['twitter_status'] = 'suspended'
                            account_info['error'] = errors[0].get('detail', 'Account suspended')
                        elif 'locked' in error_detail or 'locked' in error_title:
                            account_info['twitter_status'] = 'locked'
                            account_info['error'] = errors[0].get('detail', 'Account is locked')
                        elif 'restricted' in error_detail:
                            account_info['twitter_status'] = 'restricted'
                            account_info['error'] = errors[0].get('detail', 'Account is restricted')
                        elif 'deactivated' in error_detail:
                            account_info['twitter_status'] = 'deactivated'
                            account_info['error'] = errors[0].get('detail', 'Account is deactivated')
                        else:
                            account_info['twitter_status'] = 'forbidden'
                            account_info['error'] = errors[0].get('detail', 'Access forbidden')
                    else:
                        account_info['twitter_status'] = 'forbidden'
                        account_info['error'] = 'Access forbidden'
                
                elif response.status_code == 404:
                    account_info['twitter_status'] = 'not_found'
                    account_info['error'] = 'Account not found'
                
                elif response.status_code == 429:
                    account_info['twitter_status'] = 'rate_limited'
                    account_info['error'] = 'Rate limit exceeded'
                
                else:
                    account_info['twitter_status'] = 'error'
                    account_info['error'] = f'HTTP {response.status_code}: {response.text[:100]}'
                    
            except Exception as e:
                account_info['twitter_status'] = 'error'
                account_info['error'] = str(e)
            
            results.append(account_info)
        
        # Summary statistics with account names for problematic accounts
        problem_statuses = ['suspended', 'locked', 'restricted', 'deactivated', 'token_expired', 'unauthorized']
        
        summary = {
            'total': len(results),
            'active': len([r for r in results if r['twitter_status'] == 'active']),
            'suspended': [r['username'] for r in results if r['twitter_status'] == 'suspended'],
            'locked': [r['username'] for r in results if r['twitter_status'] == 'locked'],
            'restricted': [r['username'] for r in results if r['twitter_status'] == 'restricted'],
            'protected': len([r for r in results if r['twitter_status'] == 'protected']),
            'deactivated': [r['username'] for r in results if r['twitter_status'] == 'deactivated'],
            'token_expired': [r['username'] for r in results if r['twitter_status'] == 'token_expired'],
            'unauthorized': [r['username'] for r in results if r['twitter_status'] == 'unauthorized'],
            'other_issues': [r['username'] for r in results if r['twitter_status'] not in ['active', 'suspended', 'locked', 'restricted', 'protected', 'deactivated', 'token_expired', 'unauthorized']]
        }
        
        return jsonify({
            'summary': summary,
            'accounts': results,
            'timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# List Management Endpoints
@app.route('/api/v1/lists', methods=['POST'])
def create_list():
    """Create a new Twitter list"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Required fields
    if 'name' not in data:
        return jsonify({'error': 'name is required'}), 400
    if 'owner_account_id' not in data:
        return jsonify({'error': 'owner_account_id is required'}), 400
    
    name = data['name']
    description = data.get('description', '')
    mode = data.get('mode', 'private')
    owner_account_id = data['owner_account_id']
    
    if mode not in ['private', 'public']:
        return jsonify({'error': 'mode must be "private" or "public"'}), 400
    
    try:
        conn = get_db()
        
        # Check if owner account exists and is a list_owner
        owner = conn.execute(
            'SELECT id, username, account_type, access_token FROM twitter_account WHERE id = ?',
            (owner_account_id,)
        ).fetchone()
        
        if not owner:
            conn.close()
            return jsonify({'error': 'Owner account not found'}), 404
        
        if owner['account_type'] != 'list_owner':
            conn.close()
            return jsonify({'error': 'Account must be of type "list_owner" to create lists'}), 400
        
        # Create list on Twitter
        access_token = decrypt_token(owner['access_token'])
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        list_data = {
            'name': name,
            'description': description,
            'private': mode == 'private'
        }
        
        response = requests.post(
            'https://api.twitter.com/2/lists',
            headers=headers,
            json=list_data
        )
        
        if response.status_code != 201:
            conn.close()
            return jsonify({
                'error': 'Failed to create list on Twitter',
                'details': response.json()
            }), response.status_code
        
        twitter_list = response.json()['data']
        list_id = twitter_list['id']
        
        # Save to database
        cursor = conn.execute(
            '''INSERT INTO twitter_list (list_id, name, description, mode, owner_account_id) 
               VALUES (?, ?, ?, ?, ?)''',
            (list_id, name, description, mode, owner_account_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List created successfully',
            'list': {
                'id': cursor.lastrowid,
                'list_id': list_id,
                'name': name,
                'description': description,
                'mode': mode,
                'owner_account_id': owner_account_id,
                'owner_username': owner['username']
            }
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists', methods=['GET'])
def get_lists():
    """Get all lists"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    owner_account_id = request.args.get('owner_account_id')
    
    try:
        conn = get_db()
        
        if owner_account_id:
            cursor = conn.execute('''
                SELECT l.*, a.username as owner_username 
                FROM twitter_list l
                JOIN twitter_account a ON l.owner_account_id = a.id
                WHERE l.owner_account_id = ?
                ORDER BY l.created_at DESC
            ''', (owner_account_id,))
        else:
            cursor = conn.execute('''
                SELECT l.*, a.username as owner_username 
                FROM twitter_list l
                JOIN twitter_account a ON l.owner_account_id = a.id
                ORDER BY l.created_at DESC
            ''')
        
        lists = cursor.fetchall()
        
        # Get member counts
        result = []
        for lst in lists:
            member_count = conn.execute(
                'SELECT COUNT(*) as count FROM list_membership WHERE list_id = ?',
                (lst['id'],)
            ).fetchone()['count']
            
            result.append({
                'id': lst['id'],
                'list_id': lst['list_id'],
                'name': lst['name'],
                'description': lst['description'],
                'mode': lst['mode'],
                'owner_account_id': lst['owner_account_id'],
                'owner_username': lst['owner_username'],
                'member_count': member_count,
                'created_at': lst['created_at'],
                'updated_at': lst['updated_at']
            })
        
        conn.close()
        
        return jsonify({
            'lists': result,
            'total': len(result)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists/<int:list_id>', methods=['GET'])
def get_list(list_id):
    """Get specific list details"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get list details
        lst = conn.execute('''
            SELECT l.*, a.username as owner_username 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get members
        members_cursor = conn.execute('''
            SELECT a.id, a.username, a.status, lm.added_at
            FROM list_membership lm
            JOIN twitter_account a ON lm.account_id = a.id
            WHERE lm.list_id = ?
            ORDER BY lm.added_at DESC
        ''', (list_id,))
        
        members = []
        for member in members_cursor:
            members.append({
                'id': member['id'],
                'username': member['username'],
                'status': member['status'],
                'added_at': member['added_at']
            })
        
        conn.close()
        
        return jsonify({
            'list': {
                'id': lst['id'],
                'list_id': lst['list_id'],
                'name': lst['name'],
                'description': lst['description'],
                'mode': lst['mode'],
                'owner_account_id': lst['owner_account_id'],
                'owner_username': lst['owner_username'],
                'created_at': lst['created_at'],
                'updated_at': lst['updated_at']
            },
            'members': members,
            'member_count': len(members)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists/<int:list_id>', methods=['PUT'])
def update_list(list_id):
    """Update list details"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Update on Twitter
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        
        if update_data:
            response = requests.put(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}',
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                conn.close()
                return jsonify({
                    'error': 'Failed to update list on Twitter',
                    'details': response.json()
                }), response.status_code
        
        # Update in database
        if 'name' in data:
            conn.execute(
                'UPDATE twitter_list SET name = ?, updated_at = ? WHERE id = ?',
                (data['name'], datetime.now(UTC).isoformat(), list_id)
            )
        if 'description' in data:
            conn.execute(
                'UPDATE twitter_list SET description = ?, updated_at = ? WHERE id = ?',
                (data['description'], datetime.now(UTC).isoformat(), list_id)
            )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List updated successfully',
            'list_id': list_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists/<int:list_id>', methods=['DELETE'])
def delete_list(list_id):
    """Delete a list"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token, a.username 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Delete from Twitter
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.delete(
            f'https://api.twitter.com/2/lists/{lst["list_id"]}',
            headers=headers
        )
        
        if response.status_code != 200:
            conn.close()
            return jsonify({
                'error': 'Failed to delete list on Twitter',
                'details': response.json()
            }), response.status_code
        
        # Delete from database (cascade will delete memberships)
        conn.execute('DELETE FROM twitter_list WHERE id = ?', (list_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List deleted successfully',
            'list_name': lst['name'],
            'owner_username': lst['username']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# List Membership Endpoints
@app.route('/api/v1/lists/<int:list_id>/members', methods=['POST'])
def add_list_members(list_id):
    """Add accounts to a list"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data or 'account_ids' not in data:
        return jsonify({'error': 'account_ids array is required'}), 400
    
    account_ids = data['account_ids']
    if not isinstance(account_ids, list):
        return jsonify({'error': 'account_ids must be an array'}), 400
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        added = []
        failed = []
        
        for account_id in account_ids:
            # Get account details
            account = conn.execute(
                'SELECT id, username FROM twitter_account WHERE id = ?',
                (account_id,)
            ).fetchone()
            
            if not account:
                failed.append({
                    'account_id': account_id,
                    'error': 'Account not found'
                })
                continue
            
            # Check if already member
            existing = conn.execute(
                'SELECT id FROM list_membership WHERE list_id = ? AND account_id = ?',
                (list_id, account_id)
            ).fetchone()
            
            if existing:
                failed.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': 'Already a member'
                })
                continue
            
            # Get Twitter user ID
            user_response = requests.get(
                f'https://api.twitter.com/2/users/by/username/{account["username"]}',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if user_response.status_code != 200:
                failed.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': 'Failed to get Twitter user ID'
                })
                continue
            
            twitter_user_id = user_response.json()['data']['id']
            
            # Add to list on Twitter
            add_response = requests.post(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}/members',
                headers=headers,
                json={'user_id': twitter_user_id}
            )
            
            if add_response.status_code == 200:
                # Add to database
                conn.execute(
                    'INSERT INTO list_membership (list_id, account_id) VALUES (?, ?)',
                    (list_id, account_id)
                )
                added.append({
                    'account_id': account_id,
                    'username': account['username']
                })
            else:
                failed.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': add_response.json().get('detail', 'Failed to add to Twitter list')
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Processed {len(account_ids)} accounts',
            'added': added,
            'failed': failed,
            'added_count': len(added),
            'failed_count': len(failed)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists/<int:list_id>/members', methods=['GET'])
def get_list_members(list_id):
    """Get members of a list"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check if list exists
        lst = conn.execute(
            'SELECT id, name FROM twitter_list WHERE id = ?',
            (list_id,)
        ).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get members
        cursor = conn.execute('''
            SELECT a.id, a.username, a.status, a.account_type, lm.added_at
            FROM list_membership lm
            JOIN twitter_account a ON lm.account_id = a.id
            WHERE lm.list_id = ?
            ORDER BY lm.added_at DESC
        ''', (list_id,))
        
        members = []
        for member in cursor:
            members.append({
                'id': member['id'],
                'username': member['username'],
                'status': member['status'],
                'account_type': member['account_type'] if 'account_type' in member.keys() else 'managed',
                'added_at': member['added_at']
            })
        
        conn.close()
        
        return jsonify({
            'list_id': list_id,
            'list_name': lst['name'],
            'members': members,
            'total': len(members)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/lists/<int:list_id>/members/<int:account_id>', methods=['DELETE'])
def remove_list_member(list_id, account_id):
    """Remove an account from a list"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get account details
        account = conn.execute(
            'SELECT id, username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Check membership
        membership = conn.execute(
            'SELECT id FROM list_membership WHERE list_id = ? AND account_id = ?',
            (list_id, account_id)
        ).fetchone()
        
        if not membership:
            conn.close()
            return jsonify({'error': 'Account is not a member of this list'}), 404
        
        access_token = decrypt_token(lst['access_token'])
        
        # Get Twitter user ID
        user_response = requests.get(
            f'https://api.twitter.com/2/users/by/username/{account["username"]}',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_response.status_code == 200:
            twitter_user_id = user_response.json()['data']['id']
            
            # Remove from Twitter list
            remove_response = requests.delete(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}/members/{twitter_user_id}',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if remove_response.status_code != 200:
                conn.close()
                return jsonify({
                    'error': 'Failed to remove from Twitter list',
                    'details': remove_response.json()
                }), remove_response.status_code
        
        # Remove from database
        conn.execute(
            'DELETE FROM list_membership WHERE list_id = ? AND account_id = ?',
            (list_id, account_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Account removed from list successfully',
            'list_id': list_id,
            'account_id': account_id,
            'username': account['username']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Cleanup Endpoints

@app.route('/api/v1/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete a specific account and its associated tweets"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check if account exists
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Delete associated tweets first
        deleted_tweets = conn.execute(
            'DELETE FROM tweet WHERE twitter_account_id = ?',
            (account_id,)
        ).rowcount
        
        # Delete the account
        conn.execute(
            'DELETE FROM twitter_account WHERE id = ?',
            (account_id,)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Account @{account["username"]} deleted successfully',
            'deleted_tweets': deleted_tweets
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/accounts/cleanup', methods=['POST'])
def cleanup_inactive_accounts():
    """Delete inactive accounts (failed, suspended, or custom status)"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    # Get status filter from request
    data = request.get_json() or {}
    statuses_to_delete = data.get('statuses', ['failed', 'suspended', 'inactive'])
    
    try:
        conn = get_db()
        
        # Get accounts to delete
        placeholders = ','.join('?' * len(statuses_to_delete))
        accounts = conn.execute(
            f'SELECT id, username, status FROM twitter_account WHERE status IN ({placeholders})',
            statuses_to_delete
        ).fetchall()
        
        results = {
            'deleted_accounts': [],
            'deleted_tweets_total': 0
        }
        
        for account in accounts:
            # Delete tweets for this account
            deleted_tweets = conn.execute(
                'DELETE FROM tweet WHERE twitter_account_id = ?',
                (account['id'],)
            ).rowcount
            
            # Delete the account
            conn.execute(
                'DELETE FROM twitter_account WHERE id = ?',
                (account['id'],)
            )
            
            results['deleted_accounts'].append({
                'id': account['id'],
                'username': account['username'],
                'status': account['status'],
                'deleted_tweets': deleted_tweets
            })
            results['deleted_tweets_total'] += deleted_tweets
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Cleaned up {len(accounts)} inactive accounts',
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/cleanup', methods=['POST'])
def cleanup_tweets():
    """Delete tweets by status or age"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json() or {}
    statuses = data.get('statuses', [])
    days_old = data.get('days_old')
    account_id = data.get('account_id')
    
    if not statuses and not days_old:
        return jsonify({'error': 'Provide either statuses or days_old parameter'}), 400
    
    try:
        conn = get_db()
        
        # Build query
        query = 'DELETE FROM tweet WHERE 1=1'
        params = []
        
        if statuses:
            placeholders = ','.join('?' * len(statuses))
            query += f' AND status IN ({placeholders})'
            params.extend(statuses)
        
        if days_old:
            cutoff_date = (datetime.now(UTC) - timedelta(days=days_old)).isoformat()
            query += ' AND created_at < ?'
            params.append(cutoff_date)
        
        if account_id:
            query += ' AND twitter_account_id = ?'
            params.append(account_id)
        
        # Get count before deletion for reporting
        count_query = query.replace('DELETE FROM', 'SELECT COUNT(*) FROM')
        count = conn.execute(count_query, params).fetchone()[0]
        
        # Execute deletion
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Deleted {count} tweets',
            'criteria': {
                'statuses': statuses,
                'days_old': days_old,
                'account_id': account_id
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tweets/<int:tweet_id>', methods=['DELETE'])
def delete_tweet(tweet_id):
    """Delete a specific tweet"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check if tweet exists
        tweet = conn.execute(
            'SELECT id, content, status FROM tweet WHERE id = ?',
            (tweet_id,)
        ).fetchone()
        
        if not tweet:
            conn.close()
            return jsonify({'error': 'Tweet not found'}), 404
        
        # Delete the tweet
        conn.execute('DELETE FROM tweet WHERE id = ?', (tweet_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Tweet deleted successfully',
            'tweet': {
                'id': tweet['id'],
                'content': tweet['content'][:50] + '...' if len(tweet['content']) > 50 else tweet['content'],
                'status': tweet['status']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/threads/cleanup', methods=['POST'])
def cleanup_threads():
    """Delete threads based on criteria"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        data = request.get_json() or {}
        statuses = data.get('statuses', [])
        days_old = data.get('days_old')
        account_id = data.get('account_id')
        
        if not statuses and not days_old:
            return jsonify({'error': 'At least one of statuses or days_old is required'}), 400
        
        conn = get_db()
        
        # Build the query
        conditions = []
        params = []
        
        # First, get thread IDs that match our criteria
        thread_query = '''
            SELECT DISTINCT thread_id 
            FROM tweet 
            WHERE thread_id IS NOT NULL
        '''
        
        if statuses:
            # Thread with all tweets matching the status filter
            placeholders = ','.join('?' * len(statuses))
            conditions.append(f'''thread_id IN (
                SELECT thread_id 
                FROM tweet 
                WHERE thread_id IS NOT NULL 
                GROUP BY thread_id 
                HAVING COUNT(CASE WHEN status IN ({placeholders}) THEN 1 END) = COUNT(*)
            )''')
            params.extend(statuses)
        
        if days_old:
            conditions.append("thread_id IN (SELECT DISTINCT thread_id FROM tweet WHERE created_at < datetime('now', ? || ' days'))")
            params.append(f'-{days_old}')
        
        if account_id:
            conditions.append('thread_id IN (SELECT DISTINCT thread_id FROM tweet WHERE twitter_account_id = ?)')
            params.append(account_id)
        
        if conditions:
            thread_query += ' AND ' + ' AND '.join(conditions)
        
        # Get threads to delete
        threads = conn.execute(thread_query, params).fetchall()
        thread_ids = [t['thread_id'] for t in threads]
        
        if not thread_ids:
            conn.close()
            return jsonify({
                'message': 'No threads found matching criteria',
                'deleted_count': 0
            })
        
        # Get counts before deletion
        tweets_count = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE thread_id IN ({})'.format(','.join('?' * len(thread_ids))),
            thread_ids
        ).fetchone()['count']
        
        # Delete all tweets in these threads
        conn.execute(
            'DELETE FROM tweet WHERE thread_id IN ({})'.format(','.join('?' * len(thread_ids))),
            thread_ids
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Successfully deleted {len(thread_ids)} threads',
            'deleted_threads': len(thread_ids),
            'deleted_tweets': tweets_count,
            'criteria': {
                'statuses': statuses if statuses else None,
                'days_old': days_old if days_old else None,
                'account_id': account_id if account_id else None
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/thread/<thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    """Delete a specific thread and all its tweets"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check if thread exists and get tweet count
        thread_info = conn.execute(
            '''SELECT COUNT(*) as tweet_count,
                      SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted_count
               FROM tweet 
               WHERE thread_id = ?''',
            (thread_id,)
        ).fetchone()
        
        if thread_info['tweet_count'] == 0:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        # Delete all tweets in the thread
        conn.execute('DELETE FROM tweet WHERE thread_id = ?', (thread_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Thread deleted successfully',
            'thread_id': thread_id,
            'deleted_tweets': thread_info['tweet_count'],
            'posted_tweets_deleted': thread_info['posted_count']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Thread Retry Endpoints
@app.route('/api/v1/thread/retry/<thread_id>', methods=['POST'])
def retry_failed_thread(thread_id):
    """Retry posting a failed thread from where it left off"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Check thread status
        thread_check = conn.execute(
            '''SELECT COUNT(*) as total,
                      SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                      SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted,
                      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
               FROM tweet 
               WHERE thread_id = ?''',
            (thread_id,)
        ).fetchone()
        
        if thread_check['total'] == 0:
            conn.close()
            return jsonify({'error': f'Thread {thread_id} not found'}), 404
        
        if thread_check['failed'] == 0:
            conn.close()
            return jsonify({
                'error': 'No failed tweets in this thread',
                'stats': dict(thread_check)
            }), 400
        
        # Get the last successfully posted tweet in the thread (if any)
        last_posted = conn.execute(
            '''SELECT twitter_id, thread_position 
               FROM tweet 
               WHERE thread_id = ? AND status = 'posted'
               ORDER BY thread_position DESC
               LIMIT 1''',
            (thread_id,)
        ).fetchone()
        
        previous_tweet_id = last_posted['twitter_id'] if last_posted else None
        
        # Get all failed and pending tweets in order
        tweets_to_retry = conn.execute(
            '''SELECT id, twitter_account_id, content, thread_position 
               FROM tweet 
               WHERE thread_id = ? AND status IN ('failed', 'pending')
               ORDER BY thread_position''',
            (thread_id,)
        ).fetchall()
        
        if not tweets_to_retry:
            conn.close()
            return jsonify({
                'error': 'No tweets to retry',
                'stats': dict(thread_check)
            }), 404
        
        # Post tweets sequentially
        posted_tweets = []
        failed_tweets = []
        
        for tweet in tweets_to_retry:
            # Add rate limiting delay
            if posted_tweets or last_posted:  # Delay unless it's the first tweet
                delay = get_rate_limit_delay(tweet['twitter_account_id'])
                time.sleep(delay)
            
            success, result = post_to_twitter(
                tweet['twitter_account_id'], 
                tweet['content'],
                reply_to_tweet_id=previous_tweet_id
            )
            
            if success:
                # Update tweet status
                conn.execute(
                    '''UPDATE tweet 
                       SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                       WHERE id = ?''',
                    ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                )
                conn.commit()
                
                posted_tweets.append({
                    'tweet_id': tweet['id'],
                    'twitter_id': result,
                    'position': tweet['thread_position'],
                    'status': 'posted'
                })
                
                # Set this tweet as the one to reply to for the next tweet
                previous_tweet_id = result
            else:
                # Update as failed
                conn.execute(
                    'UPDATE tweet SET status = ? WHERE id = ?',
                    ('failed', tweet['id'])
                )
                conn.commit()
                
                failed_tweets.append({
                    'tweet_id': tweet['id'],
                    'position': tweet['thread_position'],
                    'status': 'failed',
                    'error': result
                })
                
                # Stop on first failure to maintain thread continuity
                break
        
        conn.close()
        
        return jsonify({
            'message': 'Thread retry completed',
            'thread_id': thread_id,
            'posted': len(posted_tweets),
            'failed': len(failed_tweets),
            'tweets': posted_tweets + failed_tweets
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/threads/reset-failed', methods=['POST'])
def reset_failed_threads():
    """Reset failed thread tweets back to pending status"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        conn = get_db()
        
        # Build query based on provided filters
        query_parts = []
        params = []
        
        if 'thread_ids' in data and data['thread_ids']:
            placeholders = ','.join('?' * len(data['thread_ids']))
            query_parts.append(f'thread_id IN ({placeholders})')
            params.extend(data['thread_ids'])
        
        if 'account_id' in data:
            query_parts.append('twitter_account_id = ?')
            params.append(data['account_id'])
        
        if 'days_old' in data:
            cutoff_date = (datetime.now(UTC) - timedelta(days=data['days_old'])).isoformat()
            query_parts.append('created_at < ?')
            params.append(cutoff_date)
        
        if not query_parts:
            conn.close()
            return jsonify({'error': 'No filter criteria provided'}), 400
        
        # First, get the thread IDs that have failed tweets
        where_clause = ' AND '.join(query_parts)
        affected_threads = conn.execute(
            f'''SELECT DISTINCT thread_id 
                FROM tweet 
                WHERE status = 'failed' AND thread_id IS NOT NULL AND {where_clause}''',
            params
        ).fetchall()
        
        if not affected_threads:
            conn.close()
            return jsonify({
                'message': 'No failed thread tweets found matching criteria',
                'count': 0
            })
        
        # Reset failed tweets to pending
        result = conn.execute(
            f'''UPDATE tweet 
                SET status = 'pending', twitter_id = NULL, posted_at = NULL, reply_to_tweet_id = NULL
                WHERE status = 'failed' AND thread_id IS NOT NULL AND {where_clause}''',
            params
        )
        
        count = result.rowcount
        conn.commit()
        
        # Get updated thread statistics
        thread_stats = []
        for thread in affected_threads:
            stats = conn.execute(
                '''SELECT thread_id,
                          COUNT(*) as total,
                          SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                   FROM tweet 
                   WHERE thread_id = ?
                   GROUP BY thread_id''',
                (thread['thread_id'],)
            ).fetchone()
            thread_stats.append(dict(stats))
        
        conn.close()
        
        return jsonify({
            'message': f'Reset {count} failed tweets to pending status',
            'count': count,
            'affected_threads': len(affected_threads),
            'thread_stats': thread_stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add route at Twitter's expected callback URL
@app.route('/auth/callback', methods=['GET'])
def auth_callback_redirect():
    """Handle OAuth callback from Twitter and display success message"""
    # Get all query parameters
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return f"<h1>OAuth Error</h1><p>{error}</p>", 400
    
    if not code or not state:
        return "<h1>Invalid OAuth callback</h1><p>Missing code or state parameter</p>", 400
    
    # Process the OAuth callback directly here
    conn = get_db()
    
    # Retrieve code_verifier from database
    oauth_data = conn.execute(
        'SELECT code_verifier FROM oauth_state WHERE state = ?',
        (state,)
    ).fetchone()
    
    if not oauth_data:
        conn.close()
        return "<h1>Invalid state</h1><p>The authorization state is invalid or expired. Please start the OAuth flow again.</p>", 400
    
    code_verifier = oauth_data['code_verifier']
    
    # Exchange code for tokens
    token_url = 'https://api.twitter.com/2/oauth2/token'
    
    auth_string = f"{TWITTER_CLIENT_ID}:{TWITTER_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'client_id': TWITTER_CLIENT_ID,
        'redirect_uri': TWITTER_CALLBACK_URL,
        'code_verifier': code_verifier
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code != 200:
        conn.close()
        return f"<h1>Token Exchange Failed</h1><p>Status: {response.status_code}</p><pre>{response.text}</pre>", 400
    
    tokens = response.json()
    access_token = tokens['access_token']
    refresh_token = tokens.get('refresh_token')
    expires_in = tokens.get('expires_in', 7200)  # Default 2 hours
    
    # Calculate token expiry time (store actual expiry, no buffer)
    token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    
    # Get user info
    user_response = requests.get(
        'https://api.twitter.com/2/users/me',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if user_response.status_code != 200:
        conn.close()
        return f"<h1>Failed to get user info</h1><p>Status: {user_response.status_code}</p><pre>{user_response.text}</pre>", 400
    
    user_data = user_response.json()['data']
    username = user_data['username']
    
    # Encrypt tokens
    encrypted_access_token = fernet.encrypt(access_token.encode()).decode()
    encrypted_refresh_token = fernet.encrypt(refresh_token.encode()).decode() if refresh_token else None
    
    # Check if account exists
    existing = conn.execute(
        'SELECT id FROM twitter_account WHERE username = ?',
        (username,)
    ).fetchone()
    
    if existing:
        # Update existing account with token metadata
        conn.execute('''
            UPDATE twitter_account 
            SET access_token = ?, 
                refresh_token = ?, 
                status = ?, 
                token_expires_at = ?,
                last_token_refresh = ?,
                refresh_failure_count = 0,
                updated_at = ? 
            WHERE username = ?
        ''', (
            encrypted_access_token, 
            encrypted_refresh_token, 
            'active', 
            token_expires_at.isoformat(),
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat(), 
            username
        ))
        account_id = existing['id']
        message = f"Account @{username} has been re-authorized successfully!"
    else:
        # Create new account with token metadata
        cursor = conn.execute('''
            INSERT INTO twitter_account 
            (username, access_token, access_token_secret, refresh_token, status, 
             token_expires_at, last_token_refresh, refresh_failure_count, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username, 
            encrypted_access_token, 
            None, 
            encrypted_refresh_token, 
            'active',
            token_expires_at.isoformat(),
            datetime.now(UTC).isoformat(),
            0,
            datetime.now(UTC).isoformat()
        ))
        account_id = cursor.lastrowid
        message = f"Account @{username} has been authorized successfully!"
    
    # Clean up oauth_state
    conn.execute('DELETE FROM oauth_state WHERE state = ?', (state,))
    
    conn.commit()
    conn.close()
    
    # Return success HTML page
    return f'''<!DOCTYPE html>
<html>
<head>
    <title>Authorization Successful</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .success {{
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .info {{
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        code {{
            background-color: #f8f9fa;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border: 1px solid #dee2e6;
        }}
    </style>
</head>
<body>
    <h1>✅ Authorization Successful!</h1>
    <div class="success">
        <h2>{message}</h2>
        <p><strong>Account ID:</strong> {account_id}</p>
        <p><strong>Username:</strong> @{username}</p>
    </div>
    
    <div class="info">
        <h3>What's Next?</h3>
        <p>You can now post tweets using this account. Here's how:</p>
    </div>
    
    <h3>1. Create a Tweet</h3>
    <pre>curl -X POST http://localhost:5555/api/v1/tweet \
  -H "X-API-Key: {VALID_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{{
    "text": "Hello from Twitter Manager API!",
    "account_id": {account_id}
  }}'</pre>
    
    <h3>2. Post the Tweet</h3>
    <pre>curl -X POST http://localhost:5555/api/v1/tweet/post/{{tweet_id}} \
  -H "X-API-Key: {VALID_API_KEY}"</pre>
    
    <p><a href="/api/v1/accounts" onclick="event.preventDefault(); alert('Remember to include the X-API-Key header!')">View All Accounts</a> | 
       <a href="/api/v1/tweets" onclick="event.preventDefault(); alert('Remember to include the X-API-Key header!')">View All Tweets</a></p>
</body>
</html>'''

# Initialize database tables
def init_database():
    """Initialize database tables"""
    try:
        conn = get_db()
        
        # Enable WAL mode once for better concurrent access
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')  # 5 seconds
        
        # Create api_key table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_key (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create twitter_account table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS twitter_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                access_token_secret TEXT,
                refresh_token TEXT,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        ''')
        
        # Create tweet table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tweet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_account_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                twitter_id TEXT,
                thread_id TEXT,
                reply_to_tweet_id TEXT,
                thread_position INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                posted_at DATETIME,
                FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id)
            )
        ''')
        
        # Create oauth_state table if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS oauth_state (
                state TEXT PRIMARY KEY,
                code_verifier TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
        ''')
        
        # Add refresh_token column to twitter_account if it doesn't exist
        try:
            conn.execute('ALTER TABLE twitter_account ADD COLUMN refresh_token TEXT')
            print("Added refresh_token column to twitter_account table")
        except:
            pass  # Column already exists
        
        # Add updated_at column if it doesn't exist
        try:
            conn.execute('ALTER TABLE twitter_account ADD COLUMN updated_at DATETIME')
            print("Added updated_at column to twitter_account table")
        except:
            pass  # Column already exists
        
        # Add token metadata columns
        try:
            conn.execute('ALTER TABLE twitter_account ADD COLUMN token_expires_at DATETIME')
            print("Added token_expires_at column to twitter_account table")
        except:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE twitter_account ADD COLUMN last_token_refresh DATETIME')
            print("Added last_token_refresh column to twitter_account table")
        except:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE twitter_account ADD COLUMN refresh_failure_count INTEGER DEFAULT 0')
            print("Added refresh_failure_count column to twitter_account table")
        except:
            pass  # Column already exists
        
        # Add account_type column to twitter_account if it doesn't exist
        try:
            conn.execute("ALTER TABLE twitter_account ADD COLUMN account_type TEXT DEFAULT 'managed'")
            print("Added account_type column to twitter_account table")
        except:
            pass  # Column already exists
        
        # Add thread support columns to tweet table if they don't exist
        try:
            conn.execute('ALTER TABLE tweet ADD COLUMN thread_id TEXT')
            print("Added thread_id column to tweet table")
        except:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE tweet ADD COLUMN reply_to_tweet_id TEXT')
            print("Added reply_to_tweet_id column to tweet table")
        except:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE tweet ADD COLUMN thread_position INTEGER')
            print("Added thread_position column to tweet table")
        except:
            pass  # Column already exists
        
        # Create twitter_list table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS twitter_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                mode TEXT DEFAULT 'private',
                owner_account_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                FOREIGN KEY (owner_account_id) REFERENCES twitter_account(id)
            )
        ''')
        
        # Create list_membership table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS list_membership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES twitter_list(id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES twitter_account(id) ON DELETE CASCADE,
                UNIQUE(list_id, account_id)
            )
        ''')
        
        # Insert API key from environment if not exists
        if VALID_API_KEY:
            key_hash = hashlib.sha256(VALID_API_KEY.encode()).hexdigest()
            try:
                conn.execute('INSERT INTO api_key (key_hash) VALUES (?)', (key_hash,))
                print("API key added to database")
            except sqlite3.IntegrityError:
                pass  # Key already exists
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == '__main__':
    print(f"Database path: {DB_PATH}")
    print(f"Database exists: {os.path.exists(DB_PATH)}")
    print(f"Twitter Callback URL: {TWITTER_CALLBACK_URL}")
    
    # Initialize database
    init_database()
    
    # Run the app
    print("\n>>> Starting Simple Twitter Manager API")
    print(">>> API endpoints available at: http://localhost:5555/api/v1/")
    print(">>> Use API key from .env file in headers: X-API-Key: <your-api-key>")
    if VALID_API_KEY == "test-api-key-replace-in-production":
        print(">>> WARNING: Using test API key. Set API_KEY in .env for production.")
    print("\nAvailable endpoints:")
    print("  GET  /api/v1/health (no auth)")
    print("  GET  /api/v1/test")
    print("  GET  /api/v1/accounts")
    print("  GET  /api/v1/accounts/<id>")
    print("  POST /api/v1/tweet")
    print("  GET  /api/v1/tweets")
    print("  GET  /api/v1/auth/twitter - Start OAuth flow")
    print("  GET/POST /api/v1/auth/callback - OAuth callback")
    print("  GET  /api/v1/stats")
    print("\nTwitter posting endpoints:")
    print("  POST /api/v1/tweet/post/<id> - Post specific tweet")
    print("  POST /api/v1/tweets/post-pending - Post pending tweets (batch mode)")
    print("  POST /api/v1/tweets/post-pending-async - Post pending tweets (async/background)")
    print("  GET  /api/v1/jobs/<job_id> - Check background job status")
    
    print("\nTweet retry endpoints:")
    print("  POST /api/v1/tweet/retry/<id> - Retry specific failed tweet")
    print("  POST /api/v1/tweets/retry-failed - Retry failed tweets (batch mode)")
    print("  POST /api/v1/tweets/reset-failed - Reset failed tweets to pending")
    
    print("\nThread retry endpoints:")
    print("  POST /api/v1/thread/retry/<thread_id> - Retry failed thread from where it left off")
    print("  POST /api/v1/threads/reset-failed - Reset failed thread tweets to pending")
    
    print("\nToken health endpoints:")
    print("  GET  /api/v1/accounts/token-health - Check token health for all accounts")
    print("  POST /api/v1/accounts/<id>/refresh-token - Manually refresh token for account")
    print("  POST /api/v1/accounts/refresh-tokens - Refresh all expiring tokens")
    print("  POST /api/v1/accounts/<id>/clear-failures - Clear refresh failure count")
    print("  GET  /api/v1/accounts/check-twitter-status - Check if accounts are suspended/locked")
    print("\nAccount type management:")
    print("  POST   /api/v1/accounts/<id>/set-type - Set account type (managed/list_owner)")
    print("  GET    /api/v1/accounts?type=list_owner - Get accounts by type")
    print("\nList management endpoints:")
    print("  POST   /api/v1/lists - Create a new list")
    print("  GET    /api/v1/lists - Get all lists")
    print("  GET    /api/v1/lists/<id> - Get list details")
    print("  PUT    /api/v1/lists/<id> - Update list")
    print("  DELETE /api/v1/lists/<id> - Delete list")
    print("\nList membership endpoints:")
    print("  POST   /api/v1/lists/<id>/members - Add accounts to list")
    print("  GET    /api/v1/lists/<id>/members - Get list members")
    print("  DELETE /api/v1/lists/<id>/members/<account_id> - Remove from list")
    print("\nCleanup endpoints:")
    print("  DELETE /api/v1/accounts/<id> - Delete account and its tweets")
    print("  POST   /api/v1/accounts/cleanup - Delete inactive accounts")
    print("  DELETE /api/v1/tweets/<id> - Delete specific tweet")
    print("  POST   /api/v1/tweets/cleanup - Delete tweets by criteria")
    print("\nMock mode is DISABLED - tweets will be posted to Twitter!")
    
    app.run(debug=True, port=5555)