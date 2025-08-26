"""
OAuth 1.0a Service for Twitter Profile Updates

This service handles OAuth 1.0a authorization specifically for profile update capabilities.
It operates completely independently from the existing OAuth 2.0 system to avoid conflicts.
"""

import os
import secrets
import requests
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.core.config import Config
from app.db.database import get_db
from app.utils.security import encrypt_token, decrypt_token

# Import OAuth 1.0a for profile updates
try:
    from requests_oauthlib import OAuth1Session
    OAUTH1_AVAILABLE = True
except ImportError:
    OAUTH1_AVAILABLE = False


class OAuth1Service:
    """
    OAuth 1.0a service for Twitter profile update capabilities.
    Completely separate from OAuth 2.0 - no conflicts with existing tokens.
    """
    
    def __init__(self):
        self.api_key = Config.TWITTER_API_KEY
        self.api_secret = Config.TWITTER_API_SECRET
        self.callback_url = Config.TWITTER_OAUTH1_CALLBACK_URL
        
        if not self.api_key or not self.api_secret:
            raise ValueError("OAuth 1.0a credentials not configured. Set TWITTER_API_KEY and TWITTER_API_SECRET environment variables.")
    
    def get_authorization_url(self, account_id):
        """
        Generate OAuth 1.0a authorization URL for an existing account.
        
        Args:
            account_id: Database ID of the existing Twitter account
            
        Returns:
            tuple: (authorization_url, oauth_token_secret) or (None, error_message)
        """
        if not OAUTH1_AVAILABLE:
            return None, "requests-oauthlib not installed"
        
        try:
            # Verify account exists and doesn't already have OAuth 1.0a tokens
            conn = get_db()
            account = conn.execute(
                'SELECT id, username, oauth1_access_token FROM twitter_account WHERE id = ?',
                (account_id,)
            ).fetchone()
            
            if not account:
                conn.close()
                return None, "Account not found"
            
            if account['oauth1_access_token']:
                conn.close()
                return None, f"Account @{account['username']} already has OAuth 1.0a tokens for profile updates"
            
            # Create OAuth 1.0a session
            oauth = OAuth1Session(
                client_key=self.api_key,
                client_secret=self.api_secret,
                callback_uri=self.callback_url
            )
            
            # Get request token
            request_token_url = 'https://api.twitter.com/oauth/request_token'
            fetch_response = oauth.fetch_request_token(request_token_url)
            
            oauth_token = fetch_response.get('oauth_token')
            oauth_token_secret = fetch_response.get('oauth_token_secret')
            
            # Store request token temporarily (linked to account_id)
            request_token_state = secrets.token_urlsafe(32)
            
            conn.execute('''
                INSERT OR REPLACE INTO oauth1_request_tokens 
                (state, account_id, oauth_token, oauth_token_secret, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                request_token_state, 
                account_id, 
                oauth_token, 
                encrypt_token(oauth_token_secret), 
                datetime.now(UTC).isoformat()
            ))
            conn.commit()
            conn.close()
            
            # Generate authorization URL
            authorization_url = oauth.authorization_url('https://api.twitter.com/oauth/authorize')
            
            # Add state parameter to track the account
            authorization_url += f"&state={request_token_state}"
            
            return authorization_url, request_token_state
            
        except Exception as e:
            return None, f"Error generating OAuth 1.0a authorization URL: {str(e)}"
    
    def handle_callback(self, oauth_token, oauth_verifier, state=None):
        """
        Handle OAuth 1.0a callback and exchange for access tokens.
        
        Args:
            oauth_token: OAuth token from callback
            oauth_verifier: OAuth verifier from callback
            state: State parameter to identify the account
            
        Returns:
            tuple: (success, result_dict_or_error_message)
        """
        if not OAUTH1_AVAILABLE:
            return False, "requests-oauthlib not installed"
        
        try:
            conn = get_db()
            
            # Find the request token data
            if state:
                # Use state to find the account
                request_data = conn.execute(
                    'SELECT * FROM oauth1_request_tokens WHERE state = ? AND oauth_token = ?',
                    (state, oauth_token)
                ).fetchone()
            else:
                # Fallback: find by oauth_token only
                request_data = conn.execute(
                    'SELECT * FROM oauth1_request_tokens WHERE oauth_token = ?',
                    (oauth_token,)
                ).fetchone()
            
            if not request_data:
                conn.close()
                return False, "Invalid or expired OAuth 1.0a request token"
            
            account_id = request_data['account_id']
            oauth_token_secret = decrypt_token(request_data['oauth_token_secret'])
            
            # Get account info
            account = conn.execute(
                'SELECT username FROM twitter_account WHERE id = ?',
                (account_id,)
            ).fetchone()
            
            if not account:
                conn.close()
                return False, "Account not found"
            
            # Create OAuth 1.0a session with request token
            oauth = OAuth1Session(
                client_key=self.api_key,
                client_secret=self.api_secret,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret,
                verifier=oauth_verifier
            )
            
            # Exchange for access token
            access_token_url = 'https://api.twitter.com/oauth/access_token'
            oauth_tokens = oauth.fetch_access_token(access_token_url)
            
            access_token = oauth_tokens.get('oauth_token')
            access_token_secret = oauth_tokens.get('oauth_token_secret')
            twitter_user_id = oauth_tokens.get('user_id')
            screen_name = oauth_tokens.get('screen_name')
            
            # Verify this matches the expected account
            if screen_name.lower() != account['username'].lower():
                conn.close()
                return False, f"OAuth 1.0a authorization mismatch: Expected @{account['username']}, got @{screen_name}"
            
            # Store OAuth 1.0a tokens in the account record
            conn.execute('''
                UPDATE twitter_account 
                SET oauth1_access_token = ?, 
                    oauth1_access_token_secret = ?,
                    oauth1_authorized_at = ?
                WHERE id = ?
            ''', (
                encrypt_token(access_token),
                encrypt_token(access_token_secret),
                datetime.now(UTC).isoformat(),
                account_id
            ))
            
            # Clean up request token
            conn.execute('DELETE FROM oauth1_request_tokens WHERE state = ?', (state,))
            
            conn.commit()
            conn.close()
            
            return True, {
                'account_id': account_id,
                'username': account['username'],
                'twitter_user_id': twitter_user_id,
                'message': f'OAuth 1.0a tokens added successfully for @{account["username"]}. Profile updates now enabled.'
            }
            
        except Exception as e:
            return False, f"Error handling OAuth 1.0a callback: {str(e)}"
    
    def check_oauth1_status(self, account_id):
        """
        Check if an account has OAuth 1.0a tokens for profile updates.
        
        Args:
            account_id: Database ID of the Twitter account
            
        Returns:
            dict: Status information
        """
        try:
            conn = get_db()
            account = conn.execute('''
                SELECT username, oauth1_access_token, oauth1_authorized_at 
                FROM twitter_account 
                WHERE id = ?
            ''', (account_id,)).fetchone()
            
            if not account:
                conn.close()
                return {'error': 'Account not found'}
            
            has_oauth1 = bool(account['oauth1_access_token'])
            
            result = {
                'account_id': account_id,
                'username': account['username'],
                'has_oauth1_tokens': has_oauth1,
                'profile_updates_enabled': has_oauth1
            }
            
            if has_oauth1:
                result['oauth1_authorized_at'] = account['oauth1_authorized_at']
            
            conn.close()
            return result
            
        except Exception as e:
            return {'error': f'Error checking OAuth 1.0a status: {str(e)}'}


def create_oauth1_request_tokens_table():
    """
    Create table for storing OAuth 1.0a request tokens temporarily.
    This is separate from the main account table to avoid conflicts.
    """
    try:
        conn = get_db()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS oauth1_request_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT UNIQUE NOT NULL,
                account_id INTEGER NOT NULL,
                oauth_token TEXT NOT NULL,
                oauth_token_secret TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (account_id) REFERENCES twitter_account(id) ON DELETE CASCADE
            )
        ''')
        
        # Create index for faster lookups
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_oauth1_tokens_state 
            ON oauth1_request_tokens(state)
        ''')
        
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_oauth1_tokens_account 
            ON oauth1_request_tokens(account_id)
        ''')
        
        conn.commit()
        conn.close()
        print("OAuth 1.0a request tokens table created successfully")
        
    except Exception as e:
        print(f"Error creating OAuth 1.0a request tokens table: {e}")