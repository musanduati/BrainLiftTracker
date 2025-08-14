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
    
    # Build query - exclude thread tweets from tweet_count (only count standalone changes)
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
            a.workflowy_url,
            COUNT(DISTINCT CASE WHEN t.thread_id IS NULL THEN t.id END) as tweet_count,
            COUNT(DISTINCT CASE WHEN t.status = 'pending' AND t.thread_id IS NULL THEN t.id END) as pending_tweets,
            COUNT(DISTINCT t.thread_id) as thread_count,
            COUNT(DISTINCT f.id) as follower_count
        FROM twitter_account a
        LEFT JOIN tweet t ON a.id = t.twitter_account_id
        LEFT JOIN follower f ON a.id = f.account_id AND f.status = 'active'
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
            'thread_count': account['thread_count'],
            'token_expires_at': account['token_expires_at'],
            'last_token_refresh': account['last_token_refresh'],
            'refresh_failure_count': account['refresh_failure_count'],
            'token_health': token_health,
            'account_type': account['account_type'] or 'managed',
            'display_name': account['display_name'],
            'profile_picture': account['profile_picture'],
            'followerCount': account['follower_count'],
            'workflowy_url': account['workflowy_url']
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
    
    # Get account with tweet stats - separate standalone tweets (changes) from thread tweets
    account = conn.execute('''
        SELECT 
            a.*,
            COUNT(DISTINCT CASE WHEN t.thread_id IS NULL THEN t.id END) as standalone_tweets,
            COUNT(DISTINCT CASE WHEN t.thread_id IS NOT NULL THEN t.id END) as thread_tweets,
            COUNT(DISTINCT CASE WHEN t.status = 'pending' AND t.thread_id IS NULL THEN t.id END) as pending_standalone,
            COUNT(DISTINCT CASE WHEN t.status = 'posted' AND t.thread_id IS NULL THEN t.id END) as posted_standalone,
            COUNT(DISTINCT CASE WHEN t.status = 'failed' AND t.thread_id IS NULL THEN t.id END) as failed_standalone,
            COUNT(DISTINCT t.thread_id) as total_threads,
            COUNT(DISTINCT CASE WHEN t.thread_id IS NOT NULL AND t.status = 'pending' THEN t.thread_id END) as pending_threads,
            COUNT(DISTINCT CASE WHEN t.thread_id IS NOT NULL AND t.status = 'posted' THEN t.thread_id END) as posted_threads
        FROM twitter_account a
        LEFT JOIN tweet t ON a.id = t.twitter_account_id
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
            'profile_picture': account['profile_picture'],
            'workflowy_url': account['workflowy_url']
        },
        'stats': {
            'standalone_tweets': account['standalone_tweets'],  # Changes (not part of threads)
            'thread_tweets': account['thread_tweets'],  # Tweets that are part of threads
            'pending_standalone': account['pending_standalone'],
            'posted_standalone': account['posted_standalone'],
            'failed_standalone': account['failed_standalone'],
            'total_threads': account['total_threads'],
            'pending_threads': account['pending_threads'],
            'posted_threads': account['posted_threads'],
            # Legacy fields for compatibility
            'total_tweets': account['standalone_tweets'],  # Only standalone for backward compatibility
            'pending_tweets': account['pending_standalone'],
            'posted_tweets': account['posted_standalone'],
            'failed_tweets': account['failed_standalone']
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
        'SELECT id, username FROM twitter_account WHERE id = ?',
        (account_id,)
    ).fetchone()
    
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 100)
    offset = (page - 1) * per_page
    
    # Get status filter
    status = request.args.get('status', 'active')
    
    # Get total count
    count_result = conn.execute(
        'SELECT COUNT(*) as count FROM follower WHERE account_id = ? AND status = ?',
        (account_id, status)
    ).fetchone()
    total_count = count_result['count']
    
    # Get followers with pagination
    followers = conn.execute('''
        SELECT 
            id,
            follower_username,
            follower_id,
            follower_name,
            approved_at,
            last_updated,
            status
        FROM follower
        WHERE account_id = ? AND status = ?
        ORDER BY approved_at DESC
        LIMIT ? OFFSET ?
    ''', (account_id, status, per_page, offset)).fetchall()
    
    conn.close()
    
    # Format response to match frontend expectations
    formatted_followers = []
    for follower in followers:
        formatted_followers.append({
            'id': follower['id'],
            'twitter_user_id': follower['follower_id'] or '',
            'username': follower['follower_username'],
            'display_name': follower['follower_name'] or follower['follower_username'],
            'name': follower['follower_name'] or follower['follower_username'],
            'profile_picture': None,
            'description': None,
            'verified': False,
            'followers_count': 0,
            'following_count': 0, 
            'tweet_count': 0,
            'created_at': follower['approved_at'],
            'is_approved': True,
            'approved_at': follower['approved_at'],
            'last_updated': follower['last_updated'],
            'status': follower['status']
        })
    
    return jsonify({
        'account': {
            'id': account['id'],
            'username': account['username']
        },
        'followers': formatted_followers,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page if per_page > 0 else 0
        }
    })

@accounts_bp.route('/api/v1/accounts/followers-gained', methods=['GET'])
@require_api_key
def get_followers_gained_by_time():
    """Get accounts that gained new followers within a specified time period
    
    Query Parameters:
    - time_period: Time period to filter (e.g., '1d', '7d', '30d', '1h', '24h')
    - account_id: Optional - filter for specific account
    
    Returns accounts with their new followers gained in the specified period
    """
    conn = get_db()
    
    # Get time period parameter
    time_period = request.args.get('time_period', '1d')
    account_id = request.args.get('account_id')
    
    # Parse time period
    import re
    match = re.match(r'(\d+)([hd])', time_period.lower())
    if not match:
        conn.close()
        return jsonify({'error': 'Invalid time period format. Use format like 1d, 7d, 24h'}), 400
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    # Calculate the datetime threshold
    from datetime import timedelta
    now = datetime.now(UTC)
    
    if unit == 'h':
        threshold = now - timedelta(hours=amount)
    elif unit == 'd':
        threshold = now - timedelta(days=amount)
    else:
        conn.close()
        return jsonify({'error': 'Invalid time unit. Use h for hours or d for days'}), 400
    
    # Build query to get accounts with new followers
    base_query = '''
        SELECT DISTINCT
            a.id as account_id,
            a.username as account_username,
            a.display_name as account_display_name,
            a.profile_picture as account_profile_picture,
            f.id as follower_id,
            f.follower_username,
            f.follower_id as follower_twitter_id,
            f.follower_name,
            f.approved_at,
            f.status as follower_status
        FROM twitter_account a
        INNER JOIN follower f ON a.id = f.account_id
        WHERE f.approved_at >= ?
        AND f.status = 'active'
    '''
    
    params = [threshold.isoformat()]
    
    if account_id:
        base_query += ' AND a.id = ?'
        params.append(account_id)
    
    base_query += ' ORDER BY f.approved_at DESC, a.username'
    
    followers_data = conn.execute(base_query, params).fetchall()
    
    # Get summary stats
    stats_query = '''
        SELECT 
            COUNT(DISTINCT a.id) as accounts_with_new_followers,
            COUNT(DISTINCT f.id) as total_new_followers
        FROM twitter_account a
        INNER JOIN follower f ON a.id = f.account_id
        WHERE f.approved_at >= ?
        AND f.status = 'active'
    '''
    
    stats_params = [threshold.isoformat()]
    if account_id:
        stats_query += ' AND a.id = ?'
        stats_params.append(account_id)
    
    stats = conn.execute(stats_query, stats_params).fetchone()
    
    # Group followers by account
    accounts_map = {}
    for row in followers_data:
        acc_id = row['account_id']
        if acc_id not in accounts_map:
            accounts_map[acc_id] = {
                'id': acc_id,
                'username': row['account_username'],
                'display_name': row['account_display_name'],
                'profile_picture': row['account_profile_picture'],
                'new_followers': [],
                'new_follower_count': 0
            }
        
        accounts_map[acc_id]['new_followers'].append({
            'id': row['follower_id'],
            'username': row['follower_username'],
            'twitter_id': row['follower_twitter_id'],
            'name': row['follower_name'] or row['follower_username'],
            'approved_at': row['approved_at'],
            'status': row['follower_status']
        })
        accounts_map[acc_id]['new_follower_count'] += 1
    
    # Convert to list and sort by new follower count
    accounts_list = list(accounts_map.values())
    accounts_list.sort(key=lambda x: x['new_follower_count'], reverse=True)
    
    conn.close()
    
    return jsonify({
        'time_period': time_period,
        'from_date': threshold.isoformat(),
        'to_date': now.isoformat(),
        'summary': {
            'accounts_with_new_followers': stats['accounts_with_new_followers'],
            'total_new_followers': stats['total_new_followers']
        },
        'accounts': accounts_list
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
    
    # Get all lists with their members - matching original implementation
    lists_with_members = conn.execute('''
        SELECT 
            tl.id,
            tl.list_id,
            tl.name,
            tl.description,
            tl.mode,
            tl.source,
            tl.is_managed,
            tl.last_synced_at,
            ta_owner.username as owner_username
        FROM twitter_list tl
        JOIN twitter_account ta_owner ON tl.owner_account_id = ta_owner.id
        ORDER BY tl.name
    ''').fetchall()
    
    # Build lists with their members
    lists = []
    for list_row in lists_with_members:
        # Get members for this list
        members = conn.execute('''
            SELECT 
                ta.id,
                ta.username,
                ta.display_name,
                ta.profile_picture,
                ta.account_type,
                ta.created_at,
                COUNT(DISTINCT f.id) as follower_count,
                COUNT(DISTINCT t.thread_id) as thread_count
            FROM list_membership lm
            JOIN twitter_account ta ON lm.account_id = ta.id
            LEFT JOIN follower f ON ta.id = f.account_id AND f.status = 'active'
            LEFT JOIN tweet t ON ta.id = t.twitter_account_id
            WHERE lm.list_id = ?
            GROUP BY ta.id, ta.username, ta.display_name, ta.profile_picture, ta.account_type, ta.created_at
        ''', (list_row['id'],)).fetchall()
        
        # Format members
        formatted_members = []
        for member in members:
            formatted_members.append({
                'id': member['id'],
                'username': member['username'],
                'displayName': member['display_name'] if member['display_name'] else member['username'],
                'profilePicture': member['profile_picture'],
                'account_type': member['account_type'],
                'followerCount': member['follower_count'],
                'threadCount': member['thread_count'],
                'createdAt': member['created_at']
            })
        
        lists.append({
            'id': list_row['id'],
            'list_id': list_row['list_id'],
            'name': list_row['name'],
            'description': list_row['description'],
            'mode': list_row['mode'],
            'source': list_row['source'],
            'is_managed': bool(list_row['is_managed']),
            'owner_username': list_row['owner_username'],
            'last_synced_at': list_row['last_synced_at'],
            'member_count': len(formatted_members),
            'members': formatted_members
        })
    
    # Get accounts not in any list
    unassigned_accounts = conn.execute('''
        SELECT 
            ta.id,
            ta.username,
            ta.display_name,
            ta.profile_picture,
            ta.account_type,
            ta.created_at,
            COUNT(DISTINCT f.id) as follower_count,
            COUNT(DISTINCT t.thread_id) as thread_count
        FROM twitter_account ta
        LEFT JOIN follower f ON ta.id = f.account_id AND f.status = 'active'
        LEFT JOIN tweet t ON ta.id = t.twitter_account_id
        WHERE ta.account_type = 'managed'
        AND ta.id NOT IN (
            SELECT DISTINCT account_id FROM list_membership
        )
        GROUP BY ta.id, ta.username, ta.display_name, ta.profile_picture, ta.account_type, ta.created_at
    ''').fetchall()
    
    # Format unassigned accounts with camelCase
    formatted_unassigned = []
    for account in unassigned_accounts:
        formatted_unassigned.append({
            'id': account['id'],
            'username': account['username'],
            'displayName': account['display_name'] if account['display_name'] else account['username'],
            'profilePicture': account['profile_picture'],
            'account_type': account['account_type'],
            'followerCount': account['follower_count'],
            'threadCount': account['thread_count'],
            'createdAt': account['created_at']
        })
    
    conn.close()
    
    # Return response matching original format exactly
    response = {
        'lists': lists,
        'unassigned_accounts': formatted_unassigned,
        'stats': {
            'total_lists': len(lists),
            'total_managed_accounts': len(unassigned_accounts) + sum(len([m for m in l['members'] if m.get('account_type') == 'managed']) for l in lists),
            'accounts_in_lists': sum(len([m for m in l['members'] if m.get('account_type') == 'managed']) for l in lists),
            'accounts_not_in_lists': len(unassigned_accounts)
        }
    }
    
    return jsonify(response)

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