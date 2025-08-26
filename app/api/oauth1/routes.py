"""
OAuth 1.0a API Routes for Profile Update Capabilities

These routes handle OAuth 1.0a authorization specifically for enabling
profile update capabilities on existing Twitter accounts.

Completely separate from OAuth 2.0 to avoid conflicts.
"""

from flask import Blueprint, jsonify, request, redirect
from app.utils.security import require_api_key
from app.services.oauth1_service import OAuth1Service

oauth1_bp = Blueprint('oauth1', __name__)


@oauth1_bp.route('/api/v1/accounts/<int:account_id>/enable-profile-updates', methods=['POST'])
@require_api_key
def enable_profile_updates(account_id):
    """
    Generate OAuth 1.0a authorization URL to enable profile updates for an existing account.
    
    This does NOT interfere with existing OAuth 2.0 tokens.
    It adds OAuth 1.0a capability to an account that already has OAuth 2.0 tokens.
    """
    try:
        oauth1_service = OAuth1Service()
        auth_url, state = oauth1_service.get_authorization_url(account_id)
        
        if not auth_url:
            return jsonify({
                'error': 'Failed to generate OAuth 1.0a authorization URL',
                'details': state  # This will be the error message
            }), 400
        
        return jsonify({
            'message': 'OAuth 1.0a authorization URL generated',
            'account_id': account_id,
            'authorization_url': auth_url,
            'state': state,
            'instructions': [
                '1. Visit the authorization_url in a browser',
                '2. Authorize the application for profile updates',
                '3. You will be redirected back automatically',
                '4. Profile update capability will be enabled for this account'
            ],
            'note': 'This does not affect your existing OAuth 2.0 tokens or functionality'
        })
        
    except ValueError as e:
        return jsonify({
            'error': 'OAuth 1.0a not configured',
            'message': str(e),
            'required_env_vars': ['TWITTER_API_KEY', 'TWITTER_API_SECRET']
        }), 501
        
    except Exception as e:
        return jsonify({
            'error': 'Internal error',
            'message': str(e)
        }), 500


@oauth1_bp.route('/api/v1/accounts/<int:account_id>/profile-update-status', methods=['GET'])
@require_api_key
def get_profile_update_status(account_id):
    """
    Check if an account has OAuth 1.0a tokens for profile updates.
    """
    try:
        oauth1_service = OAuth1Service()
        status = oauth1_service.check_oauth1_status(account_id)
        
        if 'error' in status:
            return jsonify(status), 404 if 'not found' in status['error'].lower() else 400
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'error': 'Internal error',
            'message': str(e)
        }), 500


@oauth1_bp.route('/auth/oauth1/callback', methods=['GET'])
def oauth1_callback():
    """
    Handle OAuth 1.0a callback for profile update authorization.
    This is completely separate from the OAuth 2.0 callback.
    """
    # Get OAuth 1.0a callback parameters
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    state = request.args.get('state')
    denied = request.args.get('denied')
    
    if denied:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth 1.0a Authorization Denied</title>
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
                h1 {{ color: #dc3545; }}
                .denied-icon {{ font-size: 48px; margin-bottom: 1rem; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="denied-icon">❌</div>
                <h1>Authorization Denied</h1>
                <p>OAuth 1.0a authorization was denied. Profile update functionality was not enabled.</p>
                <p>Your existing OAuth 2.0 tokens and functionality remain unaffected.</p>
                <p class="close-note">You can close this window.</p>
            </div>
        </body>
        </html>
        ''', 400
    
    if not oauth_token or not oauth_verifier:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth 1.0a Callback Error</title>
        </head>
        <body>
            <h1>Invalid OAuth 1.0a Callback</h1>
            <p>Missing required parameters (oauth_token or oauth_verifier)</p>
        </body>
        </html>
        ''', 400
    
    try:
        oauth1_service = OAuth1Service()
        success, result = oauth1_service.handle_callback(oauth_token, oauth_verifier, state)
        
        if not success:
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth 1.0a Authorization Failed</title>
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
                        max-width: 500px;
                    }}
                    h1 {{ color: #dc3545; }}
                    .error-icon {{ font-size: 48px; margin-bottom: 1rem; }}
                    .error-details {{
                        background: #f8f9fa;
                        padding: 1rem;
                        border-radius: 5px;
                        margin: 1rem 0;
                        text-align: left;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">⚠️</div>
                    <h1>OAuth 1.0a Authorization Failed</h1>
                    <div class="error-details">
                        <strong>Error:</strong> {result}
                    </div>
                    <p>Your existing OAuth 2.0 tokens and functionality remain unaffected.</p>
                    <p>Please try the authorization process again or contact support.</p>
                    <p class="close-note">You can close this window.</p>
                </div>
            </body>
            </html>
            ''', 400
        
        # Success response
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Profile Updates Enabled</title>
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
                    max-width: 500px;
                }}
                h1 {{ color: #28a745; }}
                .success-icon {{ font-size: 48px; margin-bottom: 1rem; }}
                .info {{
                    background: #f7f9fa;
                    padding: 1rem;
                    border-radius: 5px;
                    margin: 1rem 0;
                }}
                .username {{ font-weight: bold; color: #1DA1F2; }}
                .feature-list {{
                    text-align: left;
                    margin: 1rem 0;
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
                <div class="success-icon">🎉</div>
                <h1>Profile Updates Enabled!</h1>
                <p>OAuth 1.0a authorization successful for <span class="username">@{result['username']}</span></p>
                
                <div class="info">
                    <p><strong>Account ID:</strong> {result['account_id']}</p>
                    <p><strong>Twitter User ID:</strong> {result['twitter_user_id']}</p>
                </div>
                
                <div class="feature-list">
                    <p><strong>New capabilities enabled:</strong></p>
                    <ul>
                        <li>✅ Bulk profile name updates via API</li>
                        <li>✅ Twitter profile display name changes</li>
                        <li>✅ Profile management through your application</li>
                    </ul>
                </div>
                
                <div class="info">
                    <p><strong>Important:</strong> Your existing OAuth 2.0 tokens remain unchanged. All current functionality (posting, deleting tweets, etc.) continues to work normally.</p>
                </div>
                
                <p class="close-note">You can now close this window and use the bulk profile update features in your application.</p>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth 1.0a System Error</title>
        </head>
        <body>
            <h1>System Error</h1>
            <p>An unexpected error occurred: {str(e)}</p>
            <p>Please contact support.</p>
        </body>
        </html>
        ''', 500


@oauth1_bp.route('/api/v1/oauth1/status', methods=['GET'])
@require_api_key  
def oauth1_system_status():
    """
    Check OAuth 1.0a system status and configuration.
    """
    try:
        oauth1_service = OAuth1Service()
        
        return jsonify({
            'oauth1_available': True,
            'api_key_configured': bool(oauth1_service.api_key),
            'api_secret_configured': bool(oauth1_service.api_secret),
            'callback_url': oauth1_service.callback_url,
            'message': 'OAuth 1.0a system is ready for profile update authorizations'
        })
        
    except ValueError as e:
        return jsonify({
            'oauth1_available': False,
            'error': str(e),
            'required_env_vars': ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_OAUTH1_CALLBACK_URL (optional)']
        }), 501
        
    except Exception as e:
        return jsonify({
            'oauth1_available': False,
            'error': f'System error: {str(e)}'
        }), 500