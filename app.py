from flask import Flask, jsonify, request, redirect
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
import hashlib
from datetime import datetime, timedelta
import json
import requests
# tweepy import moved to where it's used for Python 3.13 compatibility
import secrets
import base64
import urllib.parse
from cryptography.fernet import Fernet
import uuid

app = Flask(__name__)

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

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
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

def post_to_twitter(account_id, tweet_text, reply_to_tweet_id=None):
    """Post a tweet to Twitter using the account's credentials
    
    Args:
        account_id: The database ID of the Twitter account
        tweet_text: The text content of the tweet
        reply_to_tweet_id: Optional Twitter ID of the tweet to reply to (for threads)
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
        'timestamp': datetime.utcnow().isoformat(),
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
            (account_type, datetime.utcnow().isoformat(), account_id)
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
            (data['account_id'], data['text'], 'pending', datetime.utcnow().isoformat())
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
                    ('posted', result, datetime.utcnow().isoformat(), previous_tweet_id, tweet['id'])
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
        (state, code_verifier, datetime.utcnow().isoformat())
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
    
    # Check if account exists
    existing = conn.execute(
        'SELECT id FROM twitter_account WHERE username = ?',
        (username,)
    ).fetchone()
    
    if existing:
        # Update existing account
        conn.execute(
            'UPDATE twitter_account SET access_token = ?, refresh_token = ?, status = ?, updated_at = ? WHERE username = ?',
            (encrypted_access_token, encrypted_refresh_token, 'active', datetime.utcnow().isoformat(), username)
        )
        account_id = existing['id']
    else:
        # Create new account
        cursor = conn.execute(
            'INSERT INTO twitter_account (username, access_token, access_token_secret, refresh_token, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (username, encrypted_access_token, None, encrypted_refresh_token, 'active', datetime.utcnow().isoformat())
        )
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
                ('posted', result, datetime.utcnow().isoformat(), tweet_id)
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
    """Post all pending tweets"""
    if not check_api_key():
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = get_db()
        
        # Get all pending tweets
        pending_tweets = conn.execute(
            'SELECT * FROM tweet WHERE status = "pending" ORDER BY created_at'
        ).fetchall()
        
        results = {
            'total': len(pending_tweets),
            'posted': 0,
            'failed': 0,
            'details': []
        }
        
        for tweet in pending_tweets:
            success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
            
            if success:
                # Update to posted
                conn.execute(
                    'UPDATE tweet SET status = ?, twitter_id = ?, posted_at = ? WHERE id = ?',
                    ('posted', result, datetime.utcnow().isoformat(), tweet['id'])
                )
                results['posted'] += 1
                results['details'].append({
                    'tweet_id': tweet['id'],
                    'status': 'posted',
                    'twitter_tweet_id': result
                })
            else:
                # Update to failed
                conn.execute(
                    'UPDATE tweet SET status = ? WHERE id = ?',
                    ('failed', tweet['id'])
                )
                results['failed'] += 1
                results['details'].append({
                    'tweet_id': tweet['id'],
                    'status': 'failed',
                    'error': result
                })
        
        conn.commit()
        conn.close()
        
        return jsonify(results)
        
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
                (data['name'], datetime.utcnow().isoformat(), list_id)
            )
        if 'description' in data:
            conn.execute(
                'UPDATE twitter_list SET description = ?, updated_at = ? WHERE id = ?',
                (data['description'], datetime.utcnow().isoformat(), list_id)
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
            cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
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
        # Update existing account
        conn.execute(
            'UPDATE twitter_account SET access_token = ?, refresh_token = ?, status = ?, updated_at = ? WHERE username = ?',
            (encrypted_access_token, encrypted_refresh_token, 'active', datetime.utcnow().isoformat(), username)
        )
        account_id = existing['id']
        message = f"Account @{username} has been re-authorized successfully!"
    else:
        # Create new account
        cursor = conn.execute(
            'INSERT INTO twitter_account (username, access_token, access_token_secret, refresh_token, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (username, encrypted_access_token, None, encrypted_refresh_token, 'active', datetime.utcnow().isoformat())
        )
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
    print("  POST /api/v1/tweets/post-pending - Post all pending tweets")
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