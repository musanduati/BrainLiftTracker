from flask import Blueprint, jsonify, request, redirect
import secrets
import base64
import hashlib
import urllib.parse
import requests
from datetime import datetime, timedelta, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.core.config import Config
from app.db.database import get_db
from app.utils.security import require_api_key, encrypt_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/v1/auth/twitter', methods=['GET'])
@require_api_key
def twitter_auth():
    """Get Twitter OAuth URL"""
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
        'client_id': Config.TWITTER_CLIENT_ID,
        'redirect_uri': Config.TWITTER_CALLBACK_URL,
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

@auth_bp.route('/api/v1/auth/callback', methods=['GET', 'POST'])
@require_api_key
def auth_callback():
    """Handle OAuth callback from Twitter (API endpoint version)"""
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
    
    auth_string = f"{Config.TWITTER_CLIENT_ID}:{Config.TWITTER_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'client_id': Config.TWITTER_CLIENT_ID,
        'redirect_uri': Config.TWITTER_CALLBACK_URL,
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
    encrypted_access_token = encrypt_token(access_token)
    encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
    
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

@auth_bp.route('/auth/callback', methods=['GET'])
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
    
    auth_string = f"{Config.TWITTER_CLIENT_ID}:{Config.TWITTER_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'client_id': Config.TWITTER_CLIENT_ID,
        'redirect_uri': Config.TWITTER_CALLBACK_URL,
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
    encrypted_access_token = encrypt_token(access_token)
    encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
    
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
        action = "updated"
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
        action = "added"
    
    # Clean up oauth_state
    conn.execute('DELETE FROM oauth_state WHERE state = ?', (state,))
    
    conn.commit()
    conn.close()
    
    # Return a success HTML page
    html_response = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Twitter Authorization Successful</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 2rem;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
            }}
            h1 {{
                color: #1DA1F2;
                margin-bottom: 1rem;
            }}
            .success-icon {{
                font-size: 48px;
                margin-bottom: 1rem;
            }}
            .username {{
                font-weight: bold;
                color: #14171A;
            }}
            .info {{
                margin: 1rem 0;
                padding: 1rem;
                background: #f7f9fa;
                border-radius: 5px;
            }}
            .close-note {{
                margin-top: 1.5rem;
                color: #657786;
                font-size: 0.9rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Authorization Successful!</h1>
            <p>Twitter account <span class="username">@{username}</span> has been {action}.</p>
            <div class="info">
                <p><strong>Account ID:</strong> {account_id}</p>
                <p><strong>Token Expiry:</strong> {token_expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            <p class="close-note">You can now close this window and return to your application.</p>
        </div>
    </body>
    </html>
    '''
    
    return html_response