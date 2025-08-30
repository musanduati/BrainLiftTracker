from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import requests
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key, decrypt_token
from app.utils.rate_limit import get_rate_limit_status
from app.services.twitter import refresh_twitter_token

utils_bp = Blueprint('utils', __name__)

@utils_bp.route('/api/v1/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get statistics"""
    conn = get_db()
    
    # Get account stats
    total_accounts = conn.execute('SELECT COUNT(*) as count FROM twitter_account WHERE is_visible = 1').fetchone()['count']
    active_accounts = conn.execute('SELECT COUNT(*) as count FROM twitter_account WHERE status = "active" AND is_visible = 1').fetchone()['count']
    
    # Get tweet stats
    total_tweets = conn.execute('SELECT COUNT(*) as count FROM tweet').fetchone()['count']
    pending_tweets = conn.execute('SELECT COUNT(*) as count FROM tweet WHERE status = "pending"').fetchone()['count']
    posted_tweets = conn.execute('SELECT COUNT(*) as count FROM tweet WHERE status = "posted"').fetchone()['count']
    failed_tweets = conn.execute('SELECT COUNT(*) as count FROM tweet WHERE status = "failed"').fetchone()['count']
    
    # Get thread stats
    total_threads = conn.execute('SELECT COUNT(DISTINCT thread_id) as count FROM tweet WHERE thread_id IS NOT NULL').fetchone()['count']
    
    # Get list stats
    total_lists = conn.execute('SELECT COUNT(*) as count FROM twitter_list').fetchone()['count']
    total_memberships = conn.execute('SELECT COUNT(*) as count FROM list_membership').fetchone()['count']
    
    conn.close()
    
    return jsonify({
        'accounts': {
            'total': total_accounts,
            'active': active_accounts
        },
        'tweets': {
            'total': total_tweets,
            'pending': pending_tweets,
            'posted': posted_tweets,
            'failed': failed_tweets
        },
        'threads': {
            'total': total_threads
        },
        'lists': {
            'total': total_lists,
            'total_memberships': total_memberships
        },
        'timestamp': datetime.now(UTC).isoformat()
    })

@utils_bp.route('/api/v1/user-activity-rankings', methods=['GET'])
@require_api_key
def get_user_activity_rankings():
    """Get top 10 users ranked by number of tweets and threads"""
    conn = get_db()
    
    # Get top 10 users by total activity (tweets only for now)
    rankings = conn.execute('''
        SELECT 
            a.id,
            a.username,
            a.display_name,
            a.profile_picture,
            COUNT(t.id) as tweet_count,
            SUM(CASE WHEN t.status = 'posted' THEN 1 ELSE 0 END) as posted_count,
            SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
            0 as thread_count
        FROM twitter_account a
        LEFT JOIN tweet t ON a.id = t.twitter_account_id
        GROUP BY a.id, a.username, a.display_name, a.profile_picture
        HAVING tweet_count > 0
        ORDER BY tweet_count DESC
        LIMIT 10
    ''').fetchall()
    
    result = []
    for rank, user in enumerate(rankings, 1):
        result.append({
            'rank': rank,
            'id': user['id'],
            'username': user['username'],
            'displayName': user['display_name'] or user['username'],
            'profilePicture': user['profile_picture'],
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

@utils_bp.route('/api/v1/posts', methods=['GET'])
@require_api_key
def get_posts():
    """Get unified posts data (tweets + threads)"""
    conn = get_db()
    
    # Get all tweets
    tweets = conn.execute('''
        SELECT 
            t.id,
            ta.username,
            t.content,
            t.status,
            t.posted_at,
            t.created_at,
            t.thread_id,
            'tweet' as post_type,
            ta.display_name,
            ta.profile_picture
        FROM tweet t
        LEFT JOIN twitter_account ta ON t.twitter_account_id = ta.id
        ORDER BY t.created_at DESC
    ''').fetchall()
    
    # Get all threads (from tweet table where thread_id is not null)
    threads = conn.execute('''
        SELECT 
            t.thread_id,
            ta.username,
            t.status,
            MIN(t.posted_at) as posted_at,
            MIN(t.created_at) as created_at,
            'thread' as post_type,
            COUNT(*) as tweet_count,
            ta.display_name,
            ta.profile_picture
        FROM tweet t
        LEFT JOIN twitter_account ta ON t.twitter_account_id = ta.id
        WHERE t.thread_id IS NOT NULL
        GROUP BY t.thread_id, ta.username, ta.display_name, ta.profile_picture
        ORDER BY MIN(t.created_at) DESC
    ''').fetchall()
    
    # Combine into posts list
    posts = []
    
    # Add tweets (excluding those that are part of threads)
    for tweet in tweets:
        if not tweet['thread_id']:  # Only standalone tweets
            posts.append({
                'id': f"tweet_{tweet['id']}",
                'username': tweet['username'],
                'display_name': tweet['display_name'],
                'profile_picture': tweet['profile_picture'],
                'content': tweet['content'],
                'status': tweet['status'],
                'post_type': 'tweet',
                'posted_at': tweet['posted_at'],
                'created_at': tweet['created_at']
            })
    
    # Add threads as single posts
    for thread in threads:
        posts.append({
            'id': f"thread_{thread['thread_id']}",
            'username': thread['username'],
            'display_name': thread['display_name'],
            'profile_picture': thread['profile_picture'],
            'content': f"Thread with {thread['tweet_count']} tweets",
            'status': thread['status'],
            'post_type': 'thread',
            'tweet_count': thread['tweet_count'],
            'posted_at': thread['posted_at'],
            'created_at': thread['created_at']
        })
    
    # Get statistics
    total_posts = len(posts)
    posted_count = len([p for p in posts if p['status'] == 'posted'])
    pending_count = len([p for p in posts if p['status'] == 'pending'])
    failed_count = len([p for p in posts if p['status'] == 'failed'])
    
    # Get per-account statistics
    account_stats = {}
    for post in posts:
        username = post['username']
        if username not in account_stats:
            account_stats[username] = {
                'username': username,
                'display_name': post['display_name'],
                'profile_picture': post['profile_picture'],
                'total_posts': 0,
                'posted': 0,
                'pending': 0,
                'failed': 0
            }
        
        account_stats[username]['total_posts'] += 1
        if post['status'] == 'posted':
            account_stats[username]['posted'] += 1
        elif post['status'] == 'pending':
            account_stats[username]['pending'] += 1
        elif post['status'] == 'failed':
            account_stats[username]['failed'] += 1
    
    conn.close()
    
    return jsonify({
        'posts': posts,
        'stats': {
            'total': total_posts,
            'posted': posted_count,
            'pending': pending_count,
            'failed': failed_count
        },
        'account_stats': list(account_stats.values()),
        'timestamp': datetime.now(UTC).isoformat()
    })

@utils_bp.route('/api/v1/rate-limits', methods=['GET'])
@require_api_key
def get_rate_limits():
    """Get current rate limit status for all accounts"""
    conn = get_db()
    
    accounts = conn.execute('SELECT id, username FROM twitter_account').fetchall()
    
    rate_limits = []
    for account in accounts:
        status = get_rate_limit_status(account['id'])
        rate_limits.append({
            'account_id': account['id'],
            'username': account['username'],
            **status
        })
    
    conn.close()
    
    return jsonify({
        'rate_limits': rate_limits,
        'timestamp': datetime.now(UTC).isoformat()
    })

@utils_bp.route('/api/v1/twitter/users/<username>/lists', methods=['GET'])
@require_api_key
def get_twitter_user_lists(username):
    """Get lists owned by a Twitter user"""
    try:
        conn = get_db()
        
        # Get any list_owner account for API access
        list_owner = conn.execute(
            "SELECT access_token FROM twitter_account WHERE account_type = 'list_owner' LIMIT 1"
        ).fetchone()
        
        if not list_owner:
            conn.close()
            return jsonify({'error': 'No list_owner account available'}), 404
        
        access_token = decrypt_token(list_owner['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get user ID
        user_response = requests.get(
            f'https://api.twitter.com/2/users/by/username/{username}',
            headers=headers
        )
        
        if user_response.status_code != 200:
            conn.close()
            return jsonify({'error': f'User @{username} not found'}), 404
        
        user_id = user_response.json()['data']['id']
        
        # Get user's lists
        lists_response = requests.get(
            f'https://api.twitter.com/2/users/{user_id}/owned_lists',
            headers=headers,
            params={'max_results': 100, 'list.fields': 'name,description,private,member_count'}
        )
        
        conn.close()
        
        if lists_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch lists'}), 500
        
        return jsonify({
            'username': username,
            'lists': lists_response.json().get('data', [])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@utils_bp.route('/api/v1/twitter/lists/<list_id>/members', methods=['GET'])
@require_api_key
def get_twitter_list_members(list_id):
    """Get members of a Twitter list"""
    try:
        conn = get_db()
        
        # Get any list_owner account for API access
        list_owner = conn.execute(
            "SELECT access_token FROM twitter_account WHERE account_type = 'list_owner' LIMIT 1"
        ).fetchone()
        
        if not list_owner:
            conn.close()
            return jsonify({'error': 'No list_owner account available'}), 404
        
        access_token = decrypt_token(list_owner['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get list members
        members_response = requests.get(
            f'https://api.twitter.com/2/lists/{list_id}/members',
            headers=headers,
            params={'max_results': 100, 'user.fields': 'username,name,description'}
        )
        
        conn.close()
        
        if members_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch list members'}), 500
        
        return jsonify({
            'list_id': list_id,
            'members': members_response.json().get('data', [])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@utils_bp.route('/api/v1/debug/group-concat', methods=['GET'])
@require_api_key
def debug_group_concat():
    """Debug endpoint for testing group concat functionality"""
    conn = get_db()
    
    try:
        # Test GROUP_CONCAT functionality
        result = conn.execute('''
            SELECT 
                thread_id,
                GROUP_CONCAT(content, ' | ') as concatenated_tweets
            FROM tweet
            WHERE thread_id IS NOT NULL
            GROUP BY thread_id
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'message': 'GROUP_CONCAT test',
            'results': [dict(r) for r in result]
        })
        
    except Exception as e:
        conn.close()
        return jsonify({
            'error': str(e),
            'message': 'GROUP_CONCAT may not be available in SQLite'
        }), 500

@utils_bp.route('/api/v1/db-constraints', methods=['GET'])
@require_api_key
def check_database_constraints():
    """Check foreign key constraints - for verifying CASCADE migration"""
    conn = get_db()
    constraints = {}
    
    tables_to_check = ['tweet', 'thread', 'follower', 'list_account_membership']
    
    for table in tables_to_check:
        try:
            result = conn.execute(f'PRAGMA foreign_key_list({table})').fetchall()
            constraints[table] = []
            
            for fk in result:
                # fk format: (id, seq, table, from, to, on_update, on_delete, match)
                constraints[table].append({
                    'references_table': fk[2],
                    'from_column': fk[3], 
                    'to_column': fk[4],
                    'on_update': fk[5],
                    'on_delete': fk[6]
                })
        except Exception as e:
            constraints[table] = f'Error: {str(e)}'
    
    conn.close()
    
    # Check if CASCADE migration is complete
    cascade_status = {
        'migration_complete': True,
        'issues': []
    }
    
    # Check tweet table should have CASCADE
    if 'tweet' in constraints and isinstance(constraints['tweet'], list):
        tweet_fks = constraints['tweet']
        has_cascade = any(fk['on_delete'] == 'CASCADE' for fk in tweet_fks if fk['references_table'] == 'twitter_account')
        if not has_cascade:
            cascade_status['migration_complete'] = False
            cascade_status['issues'].append('tweet table missing CASCADE constraint')
    
    return jsonify({
        'foreign_key_constraints': constraints,
        'cascade_migration_status': cascade_status,
        'environment': 'lightsail' if 'LIGHTSAIL' in str(conn) else 'local'
    })

@utils_bp.route('/api/v1/cleanup/orphaned-tweets', methods=['POST'])
@require_api_key
def cleanup_orphaned_tweets():
    """Clean up tweets from deleted accounts"""
    import shutil
    import os
    
    data = request.get_json() or {}
    dry_run = data.get('dry_run', True)
    
    # Database path - production path
    db_path = '/home/ubuntu/twitter-manager/instance/twitter_manager.db'
    if not os.path.exists(db_path):
        # Fallback to local path for development
        db_path = os.path.join('instance', 'twitter_manager.db')
    
    if not os.path.exists(db_path):
        return jsonify({'error': 'Database not found'}), 404
    
    conn = get_db()
    
    try:
        # Analyze orphaned data first
        analysis = {}
        
        # Find deleted accounts
        deleted_accounts = conn.execute("""
            SELECT id, username, status, created_at
            FROM twitter_account 
            WHERE status = 'deleted'
            ORDER BY username
        """).fetchall()
        
        # Find orphaned tweets
        orphaned_tweets = conn.execute("""
            SELECT 
                t.id,
                t.twitter_account_id,
                t.status,
                t.thread_id,
                a.username
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.status = 'deleted'
        """).fetchall()
        
        analysis = {
            'deleted_accounts_count': len(deleted_accounts),
            'orphaned_tweets_count': len(orphaned_tweets),
            'orphaned_by_status': {}
        }
        
        # Group by tweet status
        for tweet in orphaned_tweets:
            status = tweet['status']
            analysis['orphaned_by_status'][status] = analysis['orphaned_by_status'].get(status, 0) + 1
        
        if analysis['orphaned_tweets_count'] == 0:
            conn.close()
            return jsonify({
                'message': 'No orphaned tweets found',
                'analysis': analysis,
                'dry_run': dry_run,
                'cleanup_performed': False
            })
        
        result = {
            'analysis': analysis,
            'dry_run': dry_run,
            'cleanup_performed': False,
            'tweets_deleted': 0,
            'backup_path': None
        }
        
        if not dry_run:
            # Create backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{db_path}.cleanup_backup_{timestamp}"
            shutil.copy2(db_path, backup_path)
            result['backup_path'] = backup_path
            
            # Delete orphaned tweets
            cursor = conn.execute("""
                DELETE FROM tweet 
                WHERE twitter_account_id IN (
                    SELECT id FROM twitter_account WHERE status = 'deleted'
                )
            """)
            result['tweets_deleted'] = cursor.rowcount
            result['cleanup_performed'] = True
            
            conn.commit()
            
            # Verify cleanup
            remaining = conn.execute("""
                SELECT COUNT(*) as count
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE a.status = 'deleted'
            """).fetchone()
            
            result['remaining_orphaned_tweets'] = remaining['count']
        else:
            result['message'] = f"DRY RUN: Would delete {analysis['orphaned_tweets_count']} orphaned tweets"
        
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500