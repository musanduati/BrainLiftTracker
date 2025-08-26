import requests
import base64
import secrets
import time
import os
from datetime import datetime, timedelta, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.core.config import Config
from app.db.database import get_db
from app.utils.security import decrypt_token, encrypt_token, fernet
from app.utils.rate_limit import check_rate_limit, rate_limit_tracker
from app.utils.mock_mode import is_mock_mode

# Import OAuth 1.0a for profile updates
try:
    from requests_oauthlib import OAuth1
    OAUTH1_AVAILABLE = True
except ImportError:
    OAUTH1_AVAILABLE = False

def check_token_needs_refresh(token_expires_at):
    """Check if a token needs refresh (within 15 minutes of expiry)"""
    if not token_expires_at:
        return False
    
    try:
        expires_at = datetime.fromisoformat(token_expires_at)
        # Make expires_at timezone-aware if it isn't already
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        
        # Token needs refresh if within 15 minutes of expiry
        return datetime.now(UTC) >= expires_at - timedelta(minutes=15)
    except Exception as e:
        # Error checking token expiry
        return False

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
        
        auth_string = f"{Config.TWITTER_CLIENT_ID}:{Config.TWITTER_CLIENT_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'client_id': Config.TWITTER_CLIENT_ID
        }
        
        # Add exponential backoff delay for retries
        if retry_count > 0:
            delay = (2 ** retry_count) + (secrets.randbelow(1000) / 1000)
            # Retry after exponential backoff delay
            time.sleep(delay)
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            new_access_token = tokens['access_token']
            new_refresh_token = tokens.get('refresh_token', refresh_token)  # Sometimes a new refresh token is provided
            expires_in = tokens.get('expires_in', 7200)  # Default 2 hours
            
            # Encrypt new tokens
            encrypted_access_token = encrypt_token(new_access_token)
            encrypted_refresh_token = encrypt_token(new_refresh_token)
            
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
            
            # Successfully refreshed token
            return True, new_access_token
            
        else:
            # Handle refresh failure
            try:
                error_data = response.json() if 'json' in response.headers.get('content-type', '') else {}
                error_msg = error_data.get('error_description', error_data.get('error', f'HTTP {response.status_code}'))
                print(f"Token refresh failed for account {account_id}: Status {response.status_code}, Response: {response.text}")
            except:
                error_msg = f'HTTP {response.status_code}: {response.text}'
                print(f"Token refresh failed for account {account_id}: Status {response.status_code}, Raw response: {response.text}")
            
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
            
            # Failed to refresh token
            return False, error_msg
            
    except Exception as e:
        if conn:
            conn.close()
        # Exception during token refresh
        return False, str(e)

def delete_from_twitter(account_id, twitter_id, retry_after_refresh=True):
    """Delete a tweet from Twitter using the account's credentials with automatic token refresh
    
    Args:
        account_id: The database ID of the Twitter account
        twitter_id: The Twitter ID of the tweet to delete
        retry_after_refresh: Whether to retry after refreshing token (prevents infinite loops)
    
    Returns:
        tuple: (success, result_message)
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
    if is_mock_mode():
        conn.close()
        return True, "Mock delete successful"
    
    # Check rate limit before attempting to delete
    can_delete, wait_time = check_rate_limit(account_id)
    if not can_delete:
        conn.close()
        return False, f"Rate limit approaching for account. Wait {wait_time:.0f} seconds."
    
    # Check if token needs proactive refresh
    if account['token_expires_at']:
        token_expires = datetime.fromisoformat(account['token_expires_at'])
        if token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=UTC)
        if datetime.now(UTC) >= token_expires - timedelta(minutes=15):
            conn.close()
            success, result = refresh_twitter_token(account_id)
            if success:
                conn = get_db()
                account = conn.execute(
                    'SELECT * FROM twitter_account WHERE id = ?', 
                    (account_id,)
                ).fetchone()
    
    try:
        # Decrypt access token
        access_token = decrypt_token(account['access_token'])
        access_token_secret = decrypt_token(account['access_token_secret']) if account['access_token_secret'] else None
        
        # Check if OAuth 2.0 (no secret) or OAuth 1.0a (with secret)
        if access_token_secret and access_token_secret.strip():
            conn.close()
            return False, "OAuth 1.0a not supported. Please re-authorize with OAuth 2.0."
        else:
            # OAuth 2.0 - direct API call
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            print(f"Attempting to delete tweet {twitter_id} for account {account_id}")
            response = requests.delete(
                f'https://api.twitter.com/2/tweets/{twitter_id}',
                headers=headers
            )
            print(f"Delete response: Status {response.status_code}, Body: {response.text}")
            
            if response.status_code == 401 and retry_after_refresh:
                # Token expired, try to refresh
                conn.close()
                print(f"Token expired for account {account_id}, attempting refresh...")
                success, result = refresh_twitter_token(account_id)
                
                if success:
                    print(f"Token refreshed successfully for account {account_id}, retrying deletion...")
                    return delete_from_twitter(account_id, twitter_id, retry_after_refresh=False)
                else:
                    print(f"Token refresh failed for account {account_id}: {result}")
                    return False, f"Token refresh failed: {result}"
            
            if response.status_code == 429:
                # Rate limit hit
                conn.close()
                retry_after = response.headers.get('x-rate-limit-reset')
                if retry_after:
                    with rate_limit_tracker['lock']:
                        reset_time = int(retry_after)
                        rate_limit_tracker['accounts'][account_id]['reset_time'] = reset_time
                        rate_limit_tracker['accounts'][account_id]['count'] = 200
                    wait_time = reset_time - time.time()
                    error_msg = f"Rate limit hit. Reset in {wait_time:.0f} seconds"
                else:
                    error_msg = "Rate limit hit. Please wait before deleting again."
                return False, error_msg
            
            if response.status_code == 404:
                conn.close()
                return False, "Tweet not found or already deleted"
            
            if response.status_code != 200:
                conn.close()
                error_msg = f"Twitter API error (status {response.status_code}): {response.text}"
                return False, error_msg
            
            # Check if the response actually confirms deletion
            try:
                response_data = response.json()
                if response_data.get('data', {}).get('deleted') == True:
                    conn.close()
                    return True, "Tweet deleted successfully"
                else:
                    conn.close()
                    return False, f"Twitter API returned 200 but deletion not confirmed: {response.text}"
            except:
                # If we can't parse JSON, assume success based on 200 status
                conn.close()
                return True, "Tweet deleted (200 response)"
        
    except Exception as e:
        conn.close()
        error_msg = f"Exception during deletion: {str(e)}"
        return False, error_msg

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
    if is_mock_mode():
        conn.close()
        mock_tweet_id = f"mock_{datetime.now().timestamp()}"
        # Mock mode - not posting to Twitter
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
            # Token expires soon, refreshing proactively
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
                # Proactive refresh failed
                pass
    
    try:
        # Decrypt tokens
        access_token = decrypt_token(account['access_token'])
        access_token_secret = decrypt_token(account['access_token_secret']) if account['access_token_secret'] else None
        
        # Posting tweet for account
        
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
                # Access token expired, attempting refresh
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


def update_twitter_profile_name_oauth1(username, new_name, account_id=None):
    """Update Twitter profile name using OAuth 1.0a user tokens
    
    This function updates Twitter profile names using user-specific OAuth 1.0a tokens.
    If the account doesn't have OAuth 1.0a tokens, it will only update the database.
    
    Args:
        username: Twitter username (for identification)
        new_name: New display name to set
        account_id: Optional account ID (for logging/tracking only)
    
    Returns:
        tuple: (success, result_message)
    """
    if not OAUTH1_AVAILABLE:
        return False, "requests-oauthlib not installed. Please install: pip install requests-oauthlib"
    
    # Get OAuth 1.0a app credentials from environment
    api_key = os.environ.get('TWITTER_API_KEY')
    api_secret = os.environ.get('TWITTER_API_SECRET')
    
    if not api_key or not api_secret:
        return False, "OAuth 1.0a app credentials not configured. Set TWITTER_API_KEY and TWITTER_API_SECRET environment variables."
    
    # Validate inputs
    if not username or not new_name:
        return False, "Username and new_name are required"
    
    if len(new_name) > 50:
        return False, "Display name cannot exceed 50 characters"
    
    try:
        # Check if mock mode
        if is_mock_mode():
            print(f"Mock mode: Would update @{username} display name to '{new_name}'")
            return True, f"Mock update successful for @{username}"
        
        # Get user's OAuth 1.0a tokens from database
        conn = get_db()
        try:
            account = conn.execute('''
                SELECT id, username, oauth1_access_token, oauth1_access_token_secret 
                FROM twitter_account 
                WHERE username = ?
            ''', (username.replace('@', ''),)).fetchone()
            
            if not account:
                return False, f"Account @{username} not found in database"
            
            # Check if account has OAuth 1.0a tokens
            if not account['oauth1_access_token'] or not account['oauth1_access_token_secret']:
                print(f"⚠️  @{username} does not have OAuth 1.0a tokens for profile updates")
                print(f"   Action: Database-only update (Twitter profile NOT updated)")
                print(f"   Solution: Use /api/v1/accounts/{account['id']}/enable-profile-updates to authorize OAuth 1.0a")
                return True, f"Database record updated (Twitter profile NOT updated - no OAuth 1.0a tokens)"
            
            # Decrypt OAuth 1.0a tokens
            oauth1_access_token = decrypt_token(account['oauth1_access_token'])
            oauth1_access_token_secret = decrypt_token(account['oauth1_access_token_secret'])
            
            print(f"🔄 Updating Twitter profile for @{username} using OAuth 1.0a user tokens")
            
            # Create OAuth 1.0a session with user tokens
            from requests_oauthlib import OAuth1Session
            oauth = OAuth1Session(
                client_key=api_key,
                client_secret=api_secret,
                resource_owner_key=oauth1_access_token,
                resource_owner_secret=oauth1_access_token_secret
            )
            
            # X API v1.1 endpoint for profile updates
            url = 'https://api.twitter.com/1.1/account/update_profile.json'
            
            # Prepare data - only updating the name field
            data = {
                'name': new_name
            }
            
            # Make the API request
            response = oauth.post(url, data=data)
            
            print(f"Twitter API response: Status {response.status_code}")
            
            # Handle response
            if response.status_code == 200:
                try:
                    user_data = response.json()
                    updated_name = user_data.get('name', new_name)
                    print(f"✅ Successfully updated @{username} Twitter profile name to '{updated_name}'")
                    return True, f"Twitter profile updated successfully to '{updated_name}'"
                except:
                    # Response not JSON, but 200 status indicates success
                    print(f"✅ Profile update successful (200 response) for @{username}")
                    return True, f"Twitter profile updated successfully"
                    
            elif response.status_code == 401:
                error_msg = "OAuth 1.0a authentication failed. Tokens may be expired or invalid."
                print(f"❌ Profile update failed for @{username}: {error_msg}")
                return False, error_msg
                
            elif response.status_code == 403:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('errors', [{}])[0].get('message', 'Profile update forbidden')
                except:
                    error_msg = "Profile update forbidden - account may be suspended or restricted"
                print(f"❌ Profile update failed for @{username}: {error_msg}")
                return False, error_msg
                
            elif response.status_code == 404:
                error_msg = f"User @{username} not found"
                print(f"❌ Profile update failed: {error_msg}")
                return False, error_msg
                
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded for profile updates. Please wait and try again."
                print(f"⏱️ Profile update rate limited for @{username}")
                return False, error_msg
                
            else:
                # Other error status codes
                try:
                    error_data = response.json()
                    error_msg = str(error_data.get('errors', error_data))
                except:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                
                print(f"❌ Profile update failed for @{username}: Status {response.status_code}, Error: {error_msg}")
                return False, f"Twitter API error ({response.status_code}): {error_msg}"
                
        finally:
            conn.close()
            
    except Exception as e:
        error_msg = f"Exception during profile update for @{username}: {str(e)}"
        print(error_msg)
        return False, error_msg