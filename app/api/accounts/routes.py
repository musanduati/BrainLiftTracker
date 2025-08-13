from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
import requests

from app.db.database import get_db
from app.utils.security import require_api_key, decrypt_token
from app.services.twitter import refresh_twitter_token, check_token_needs_refresh

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/api/v1/accounts', methods=['GET'])
@require_api_key
def get_accounts():
    """Get all Twitter accounts"""
    conn = get_db()
    
    # Get filter parameters
    status = request.args.get('status')
    account_type = request.args.get('type')
    
    # Build query
    query = '''
        SELECT 
            a.id,
            a.username,
            a.status,
            a.created_at,
            a.updated_at,
            a.token_expires_at,
            a.last_token_refresh,
            a.refresh_failure_count,
            a.account_type,
            a.display_name,
            a.profile_picture,
            COUNT(DISTINCT t.id) as tweet_count,
            COUNT(DISTINCT CASE WHEN t.status = 'pending' THEN t.id END) as pending_tweets
        FROM twitter_account a
        LEFT JOIN tweet t ON a.id = t.twitter_account_id
        WHERE 1=1
    '''
    
    params = []
    if status:
        query += ' AND a.status = ?'
        params.append(status)
    
    if account_type:
        query += ' AND a.account_type = ?'
        params.append(account_type)
    
    query += ' GROUP BY a.id ORDER BY a.created_at DESC'
    
    accounts = conn.execute(query, params).fetchall()
    
    result = []
    for account in accounts:
        # Check token health
        token_health = 'healthy'
        if account['token_expires_at']:
            if check_token_needs_refresh(account['token_expires_at']):
                token_health = 'expiring_soon'
            
            expires_at = datetime.fromisoformat(account['token_expires_at'])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires_at:
                token_health = 'expired'
        else:
            token_health = 'unknown'
        
        if account['refresh_failure_count'] and account['refresh_failure_count'] >= 3:
            token_health = 'refresh_failed'
        
        result.append({
            'id': account['id'],
            'username': account['username'],
            'status': account['status'],
            'created_at': account['created_at'],
            'updated_at': account['updated_at'],
            'tweet_count': account['tweet_count'],
            'pending_tweets': account['pending_tweets'],
            'token_expires_at': account['token_expires_at'],
            'last_token_refresh': account['last_token_refresh'],
            'refresh_failure_count': account['refresh_failure_count'],
            'token_health': token_health,
            'account_type': account['account_type'] or 'managed',
            'display_name': account['display_name'],
            'profile_picture': account['profile_picture']
        })
    
    conn.close()
    
    return jsonify({
        'accounts': result,
        'count': len(result)
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>', methods=['GET'])
@require_api_key
def get_account(account_id):
    """Get a specific Twitter account details"""
    conn = get_db()
    
    # Get account with tweet stats
    account = conn.execute('''
        SELECT 
            a.*,
            COUNT(DISTINCT t.id) as total_tweets,
            COUNT(DISTINCT CASE WHEN t.status = 'pending' THEN t.id END) as pending_tweets,
            COUNT(DISTINCT CASE WHEN t.status = 'posted' THEN t.id END) as posted_tweets,
            COUNT(DISTINCT CASE WHEN t.status = 'failed' THEN t.id END) as failed_tweets,
            COUNT(DISTINCT th.thread_id) as total_threads
        FROM twitter_account a
        LEFT JOIN tweet t ON a.id = t.twitter_account_id
        LEFT JOIN (SELECT DISTINCT twitter_account_id, thread_id FROM tweet WHERE thread_id IS NOT NULL) th 
            ON a.id = th.twitter_account_id
        WHERE a.id = ?
        GROUP BY a.id
    ''', (account_id,)).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    # Get recent tweets
    recent_tweets = conn.execute('''
        SELECT id, content, status, created_at, posted_at, twitter_id, thread_id
        FROM tweet
        WHERE twitter_account_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (account_id,)).fetchall()
    
    # Get list memberships
    list_memberships = conn.execute('''
        SELECT l.id, l.name, l.description, l.mode
        FROM twitter_list l
        JOIN list_membership lm ON l.id = lm.list_id
        WHERE lm.account_id = ?
    ''', (account_id,)).fetchall()
    
    # Check token health
    token_health = 'healthy'
    if account['token_expires_at']:
        if check_token_needs_refresh(account['token_expires_at']):
            token_health = 'expiring_soon'
        
        expires_at = datetime.fromisoformat(account['token_expires_at'])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if datetime.now(UTC) >= expires_at:
            token_health = 'expired'
    else:
        token_health = 'unknown'
    
    if account['refresh_failure_count'] and account['refresh_failure_count'] >= 3:
        token_health = 'refresh_failed'
    
    conn.close()
    
    return jsonify({
        'account': {
            'id': account['id'],
            'username': account['username'],
            'status': account['status'],
            'created_at': account['created_at'],
            'updated_at': account['updated_at'],
            'token_expires_at': account['token_expires_at'],
            'last_token_refresh': account['last_token_refresh'],
            'refresh_failure_count': account['refresh_failure_count'],
            'token_health': token_health,
            'account_type': account['account_type'] or 'managed',
            'display_name': account['display_name'],
            'profile_picture': account['profile_picture']
        },
        'stats': {
            'total_tweets': account['total_tweets'],
            'pending_tweets': account['pending_tweets'],
            'posted_tweets': account['posted_tweets'],
            'failed_tweets': account['failed_tweets'],
            'total_threads': account['total_threads']
        },
        'recent_tweets': [dict(tweet) for tweet in recent_tweets],
        'list_memberships': [dict(list_item) for list_item in list_memberships]
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>/refresh-token', methods=['POST'])
@require_api_key
def manual_refresh_token(account_id):
    """Manually refresh token for a specific account"""
    success, result = refresh_twitter_token(account_id)
    
    if success:
        return jsonify({
            'message': 'Token refreshed successfully',
            'account_id': account_id
        })
    else:
        return jsonify({
            'error': 'Failed to refresh token',
            'details': result,
            'account_id': account_id
        }), 400

@accounts_bp.route('/api/v1/accounts/token-health', methods=['GET'])
@require_api_key
def check_token_health():
    """Check token health for all accounts"""
    conn = get_db()
    
    accounts = conn.execute('''
        SELECT 
            id,
            username,
            token_expires_at,
            last_token_refresh,
            refresh_failure_count,
            status
        FROM twitter_account
        ORDER BY username
    ''').fetchall()
    
    results = {
        'healthy': [],
        'expiring_soon': [],
        'expired': [],
        'refresh_failed': [],
        'unknown': []
    }
    
    for account in accounts:
        account_info = {
            'id': account['id'],
            'username': account['username'],
            'token_expires_at': account['token_expires_at'],
            'last_token_refresh': account['last_token_refresh'],
            'refresh_failure_count': account['refresh_failure_count'],
            'status': account['status']
        }
        
        # Check for refresh failures first
        if account['refresh_failure_count'] and account['refresh_failure_count'] >= 3:
            results['refresh_failed'].append(account_info)
        elif account['token_expires_at']:
            expires_at = datetime.fromisoformat(account['token_expires_at'])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            
            if datetime.now(UTC) >= expires_at:
                results['expired'].append(account_info)
            elif check_token_needs_refresh(account['token_expires_at']):
                results['expiring_soon'].append(account_info)
            else:
                results['healthy'].append(account_info)
        else:
            results['unknown'].append(account_info)
    
    conn.close()
    
    summary = {
        'total_accounts': len(accounts),
        'healthy': len(results['healthy']),
        'expiring_soon': len(results['expiring_soon']),
        'expired': len(results['expired']),
        'refresh_failed': len(results['refresh_failed']),
        'unknown': len(results['unknown'])
    }
    
    return jsonify({
        'summary': summary,
        'accounts': results,
        'timestamp': datetime.now(UTC).isoformat()
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>', methods=['DELETE'])
@require_api_key
def delete_account(account_id):
    """Delete a Twitter account and all associated data"""
    conn = get_db()
    
    try:
        # Check if account exists
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Delete account (cascade will handle related records)
        conn.execute('DELETE FROM twitter_account WHERE id = ?', (account_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Account @{account["username"]} deleted successfully',
            'account_id': account_id
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@accounts_bp.route('/api/v1/accounts/<int:account_id>/followers', methods=['GET'])
@require_api_key
def get_account_followers(account_id):
    """Get followers of a Twitter account"""
    conn = get_db()
    
    account = conn.execute(
        'SELECT username, access_token FROM twitter_account WHERE id = ?',
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    try:
        access_token = decrypt_token(account['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get user ID first
        user_response = requests.get(
            f'https://api.twitter.com/2/users/by/username/{account["username"]}',
            headers=headers
        )
        
        if user_response.status_code != 200:
            conn.close()
            return jsonify({'error': 'Failed to get user info'}), 500
        
        user_id = user_response.json()['data']['id']
        
        # Get followers
        followers_response = requests.get(
            f'https://api.twitter.com/2/users/{user_id}/followers',
            headers=headers,
            params={'max_results': 100, 'user.fields': 'username,name,created_at,public_metrics'}
        )
        
        conn.close()
        
        if followers_response.status_code != 200:
            return jsonify({'error': 'Failed to get followers'}), 500
        
        return jsonify({
            'account_id': account_id,
            'username': account['username'],
            'followers': followers_response.json().get('data', [])
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@accounts_bp.route('/api/v1/accounts/<int:account_id>/set-type', methods=['POST'])
@require_api_key
def set_account_type(account_id):
    """Set account type (managed or list_owner)"""
    data = request.get_json()
    if not data or 'type' not in data:
        return jsonify({'error': 'type is required'}), 400
    
    account_type = data['type']
    if account_type not in ['managed', 'list_owner']:
        return jsonify({'error': 'type must be "managed" or "list_owner"'}), 400
    
    conn = get_db()
    
    # Check if account exists
    account = conn.execute(
        'SELECT username FROM twitter_account WHERE id = ?',
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
        'type': account_type
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>/saved-followers', methods=['GET'])
@require_api_key
def get_saved_followers(account_id):
    """Get saved/approved followers for an account"""
    conn = get_db()
    
    # Check if account exists
    account = conn.execute(
        'SELECT username FROM twitter_account WHERE id = ?',
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    # Get saved followers
    followers = conn.execute('''
        SELECT 
            follower_username,
            follower_id,
            follower_name,
            approved_at,
            last_updated,
            status
        FROM follower
        WHERE account_id = ?
        ORDER BY approved_at DESC
    ''', (account_id,)).fetchall()
    
    conn.close()
    
    return jsonify({
        'account_id': account_id,
        'username': account['username'],
        'followers': [dict(f) for f in followers],
        'count': len(followers)
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>/saved-followers', methods=['POST'])
@require_api_key
def save_follower(account_id):
    """Save/approve a follower for an account"""
    data = request.get_json()
    if not data or 'username' not in data:
        return jsonify({'error': 'follower username is required'}), 400
    
    follower_username = data['username']
    follower_id = data.get('twitter_id') or data.get('follower_id')
    follower_name = data.get('name') or data.get('follower_name')
    
    conn = get_db()
    
    # Check if account exists
    account = conn.execute(
        'SELECT username FROM twitter_account WHERE id = ?',
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    try:
        # Check if follower already saved
        existing = conn.execute(
            'SELECT id FROM follower WHERE account_id = ? AND follower_username = ?',
            (account_id, follower_username)
        ).fetchone()
        
        if existing:
            # Update existing
            conn.execute('''
                UPDATE follower 
                SET follower_id = ?, follower_name = ?, last_updated = ?
                WHERE account_id = ? AND follower_username = ?
            ''', (follower_id, follower_name, datetime.now(UTC).isoformat(), account_id, follower_username))
        else:
            # Insert new
            conn.execute('''
                INSERT INTO follower (account_id, follower_username, follower_id, follower_name)
                VALUES (?, ?, ?, ?)
            ''', (account_id, follower_username, follower_id, follower_name))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Follower saved successfully',
            'account_id': account_id,
            'follower_username': follower_username
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@accounts_bp.route('/api/v1/accounts/batch-update-followers', methods=['POST'])
@require_api_key
def batch_update_followers():
    """Batch update followers for multiple accounts"""
    data = request.get_json()
    if not data or 'updates' not in data:
        return jsonify({'error': 'updates array is required'}), 400
    
    updates = data['updates']
    if not isinstance(updates, list):
        return jsonify({'error': 'updates must be an array'}), 400
    
    conn = get_db()
    results = []
    errors = []
    
    for update in updates:
        # Support both account_id and account_username for backward compatibility
        account_id = update.get('account_id')
        account_username = update.get('account_username')
        followers = update.get('followers', [])
        
        if not account_id and not account_username:
            errors.append({
                'error': 'Each update must have account_username and followers',
                'update': update
            })
            continue
        
        try:
            # If username provided instead of ID, look up the ID
            if account_username and not account_id:
                account = conn.execute(
                    'SELECT id FROM twitter_account WHERE username = ?',
                    (account_username,)
                ).fetchone()
                if not account:
                    errors.append({
                        'error': f'Account @{account_username} not found',
                        'update': update
                    })
                    continue
                account_id = account['id']
            
            for follower in followers:
                follower_username = follower.get('username')
                if not follower_username:
                    continue
                
                # Check if exists
                existing = conn.execute(
                    'SELECT id FROM follower WHERE account_id = ? AND follower_username = ?',
                    (account_id, follower_username)
                ).fetchone()
                
                if not existing:
                    conn.execute('''
                        INSERT INTO follower (account_id, follower_username, follower_id, follower_name)
                        VALUES (?, ?, ?, ?)
                    ''', (account_id, follower_username, follower.get('id'), follower.get('name')))
            
            # Get username if not provided
            if not account_username:
                account_data = conn.execute('SELECT username FROM twitter_account WHERE id = ?', (account_id,)).fetchone()
                account_username = account_data['username'] if account_data else f'account_{account_id}'
            
            results.append({
                'account_username': account_username,
                'followers_added': len([f for f in followers if f.get('username')]),
                'account_id': account_id
            })
            
        except Exception as e:
            errors.append({
                'error': str(e),
                'update': update
            })
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': 'Batch update completed',
        'results': results,
        'errors': errors,
        'summary': {
            'accounts_processed': len(results),
            'total_errors': len(errors)
        }
    })

@accounts_bp.route('/api/v1/accounts/refresh-tokens', methods=['POST'])
@require_api_key
def refresh_all_expiring_tokens():
    """Refresh tokens for all accounts that need it"""
    conn = get_db()
    
    # Get accounts with expiring tokens
    accounts = conn.execute('''
        SELECT id, username, token_expires_at, refresh_failure_count
        FROM twitter_account
        WHERE token_expires_at IS NOT NULL
        AND refresh_failure_count < 3
    ''').fetchall()
    
    results = {'refreshed': [], 'failed': [], 'skipped': []}
    
    for account in accounts:
        if not check_token_needs_refresh(account['token_expires_at']):
            results['skipped'].append({
                'id': account['id'],
                'username': account['username'],
                'reason': 'Token still valid'
            })
            continue
        
        success, result = refresh_twitter_token(account['id'])
        
        if success:
            results['refreshed'].append({
                'id': account['id'],
                'username': account['username']
            })
        else:
            results['failed'].append({
                'id': account['id'],
                'username': account['username'],
                'error': result
            })
    
    conn.close()
    
    return jsonify({
        'summary': {
            'refreshed': len(results['refreshed']),
            'failed': len(results['failed']),
            'skipped': len(results['skipped'])
        },
        'details': results
    })

@accounts_bp.route('/api/v1/accounts/<int:account_id>/clear-failures', methods=['POST'])
@require_api_key
def clear_refresh_failures(account_id):
    """Clear refresh failure count for an account"""
    conn = get_db()
    
    # Check if account exists
    account = conn.execute(
        'SELECT username, refresh_failure_count FROM twitter_account WHERE id = ?',
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    # Clear failure count
    conn.execute(
        'UPDATE twitter_account SET refresh_failure_count = 0 WHERE id = ?',
        (account_id,)
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': 'Refresh failure count cleared',
        'account_id': account_id,
        'username': account['username'],
        'previous_failure_count': account['refresh_failure_count']
    })

@accounts_bp.route('/api/v1/accounts/check-twitter-status', methods=['GET'])
@require_api_key
def check_all_accounts_twitter_status():
    """Check Twitter status for all accounts"""
    conn = get_db()
    
    accounts = conn.execute(
        'SELECT id, username, access_token FROM twitter_account'
    ).fetchall()
    
    results = []
    
    for account in accounts:
        try:
            access_token = decrypt_token(account['access_token'])
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            
            # Verify token by getting user info
            response = requests.get(
                f'https://api.twitter.com/2/users/by/username/{account["username"]}',
                headers=headers
            )
            
            if response.status_code == 200:
                user_data = response.json()['data']
                results.append({
                    'id': account['id'],
                    'username': account['username'],
                    'status': 'active',
                    'twitter_id': user_data['id'],
                    'name': user_data.get('name')
                })
            else:
                results.append({
                    'id': account['id'],
                    'username': account['username'],
                    'status': 'error',
                    'error': f'HTTP {response.status_code}'
                })
                
        except Exception as e:
            results.append({
                'id': account['id'],
                'username': account['username'],
                'status': 'error',
                'error': str(e)
            })
    
    conn.close()
    
    return jsonify({
        'accounts': results,
        'summary': {
            'total': len(results),
            'active': len([r for r in results if r['status'] == 'active']),
            'error': len([r for r in results if r['status'] == 'error'])
        }
    })

@accounts_bp.route('/api/v1/accounts/sync-profiles', methods=['POST'])
@require_api_key
def sync_account_profiles():
    """Sync Twitter profile information for all accounts"""
    conn = get_db()
    
    accounts = conn.execute(
        'SELECT id, username, access_token FROM twitter_account'
    ).fetchall()
    
    synced = []
    failed = []
    
    for account in accounts:
        try:
            access_token = decrypt_token(account['access_token'])
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            
            # Get user profile
            response = requests.get(
                f'https://api.twitter.com/2/users/by/username/{account["username"]}',
                headers=headers,
                params={'user.fields': 'name,profile_image_url'}
            )
            
            if response.status_code == 200:
                user_data = response.json()['data']
                
                # Update profile info
                conn.execute('''
                    UPDATE twitter_account 
                    SET display_name = ?, profile_picture = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    user_data.get('name'),
                    user_data.get('profile_image_url'),
                    datetime.now(UTC).isoformat(),
                    account['id']
                ))
                
                synced.append({
                    'id': account['id'],
                    'username': account['username'],
                    'display_name': user_data.get('name')
                })
            else:
                failed.append({
                    'id': account['id'],
                    'username': account['username'],
                    'error': f'HTTP {response.status_code}'
                })
                
        except Exception as e:
            failed.append({
                'id': account['id'],
                'username': account['username'],
                'error': str(e)
            })
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Synced {len(synced)} profiles',
        'synced': synced,
        'failed': failed
    })

@accounts_bp.route('/api/v1/accounts/by-lists', methods=['GET'])
@require_api_key
def get_accounts_by_lists():
    """Get accounts grouped by their list memberships"""
    conn = get_db()
    
    # Get all accounts
    accounts = conn.execute('''
        SELECT 
            a.id,
            a.username,
            a.status,
            a.account_type,
            GROUP_CONCAT(l.name, ', ') as lists
        FROM twitter_account a
        LEFT JOIN list_membership lm ON a.id = lm.account_id
        LEFT JOIN twitter_list l ON lm.list_id = l.id
        GROUP BY a.id
        ORDER BY a.username
    ''').fetchall()
    
    # Organize by list membership
    with_lists = []
    without_lists = []
    
    for account in accounts:
        account_data = {
            'id': account['id'],
            'username': account['username'],
            'status': account['status'],
            'account_type': account['account_type'],
            'lists': account['lists'].split(', ') if account['lists'] else []
        }
        
        if account['lists']:
            with_lists.append(account_data)
        else:
            without_lists.append(account_data)
    
    conn.close()
    
    return jsonify({
        'with_lists': with_lists,
        'without_lists': without_lists,
        'summary': {
            'total_accounts': len(accounts),
            'accounts_with_lists': len(with_lists),
            'accounts_without_lists': len(without_lists)
        }
    })

@accounts_bp.route('/api/v1/accounts/cleanup', methods=['POST'])
@require_api_key
def cleanup_inactive_accounts():
    """Clean up inactive accounts"""
    data = request.get_json() or {}
    days_inactive = data.get('days_inactive', 90)
    
    conn = get_db()
    
    # Find inactive accounts
    inactive_accounts = conn.execute('''
        SELECT id, username 
        FROM twitter_account 
        WHERE status != 'active' 
        OR (updated_at IS NOT NULL AND updated_at < datetime('now', ? || ' days'))
    ''', (-days_inactive,)).fetchall()
    
    deleted = []
    for account in inactive_accounts:
        # Check if account has any recent activity
        recent_tweets = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE twitter_account_id = ? AND created_at > datetime("now", "-30 days")',
            (account['id'],)
        ).fetchone()['count']
        
        if recent_tweets == 0:
            conn.execute('DELETE FROM twitter_account WHERE id = ?', (account['id'],))
            deleted.append({
                'id': account['id'],
                'username': account['username']
            })
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Deleted {len(deleted)} inactive accounts',
        'deleted': deleted
    })