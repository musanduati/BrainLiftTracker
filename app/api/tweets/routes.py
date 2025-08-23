from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import uuid
import threading
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key
from app.services.twitter import post_to_twitter, delete_from_twitter
from app.utils.rate_limit import get_rate_limit_delay
from app.utils.dok_parser import parse_dok_metadata

tweets_bp = Blueprint('tweets', __name__)

# Track background jobs
background_jobs = {}

@tweets_bp.route('/api/v1/tweet', methods=['POST'])
@require_api_key
def create_tweet():
    """Create a new tweet"""
    data = request.get_json()
    if not data or 'text' not in data or 'account_id' not in data:
        return jsonify({'error': 'Missing text or account_id'}), 400
    
    try:
        conn = get_db()
        
        # Parse DOK metadata from tweet content
        dok_type, change_type = parse_dok_metadata(data['text'])
        
        cursor = conn.execute(
            'INSERT INTO tweet (twitter_account_id, content, status, created_at, dok_type, change_type) VALUES (?, ?, ?, ?, ?, ?)',
            (data['account_id'], data['text'], 'pending', datetime.now(UTC).isoformat(), dok_type, change_type)
        )
        tweet_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        result = {
            'message': 'Tweet created successfully',
            'tweet_id': tweet_id
        }
        
        # Include DOK metadata in response if found
        if dok_type and change_type:
            result['dok_metadata'] = {
                'dok_type': dok_type,
                'change_type': change_type
            }
        
        return jsonify(result), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@tweets_bp.route('/api/v1/tweets', methods=['GET'])
@require_api_key
def get_tweets():
    """Get all tweets with optional filters"""
    conn = get_db()
    
    # Get query parameters
    status = request.args.get('status')
    account_id = request.args.get('account_id')
    limit = request.args.get('limit', 100, type=int)
    include_threads = request.args.get('include_threads', 'false').lower() == 'true'
    
    # Build query - by default exclude tweets that are part of threads
    query = '''
        SELECT t.*, a.username 
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE 1=1
        AND a.username NOT IN ('BrainLift WF-X Integration', 'klair_three')
    '''
    params = []
    
    # Exclude thread tweets unless specifically requested
    if not include_threads:
        query += ' AND t.thread_id IS NULL'
    
    if status:
        query += ' AND t.status = ?'
        params.append(status)
    
    if account_id:
        query += ' AND t.twitter_account_id = ?'
        params.append(account_id)
    
    query += ' ORDER BY t.created_at DESC LIMIT ?'
    params.append(limit)
    
    tweets = conn.execute(query, params).fetchall()
    conn.close()
    
    # Format tweets to match frontend expectations
    formatted_tweets = []
    for tweet in tweets:
        formatted_tweets.append({
            'id': tweet['id'],
            'content': tweet['content'],  # Keep as 'content' since frontend handles both 'text' and 'content'
            'status': tweet['status'],
            'created_at': tweet['created_at'],
            'posted_at': tweet['posted_at'],
            'username': tweet['username'],
            'account_id': tweet['twitter_account_id'],  # Map twitter_account_id to account_id
            'thread_id': tweet['thread_id'],  # Keep snake_case, frontend maps to camelCase
            'thread_position': tweet['thread_position'],
            'twitter_id': tweet['twitter_id'],
            'reply_to_tweet_id': tweet['reply_to_tweet_id'],
            'dok_type': tweet['dok_type'],
            'change_type': tweet['change_type']
        })
    
    return jsonify({
        'tweets': formatted_tweets,
        'count': len(formatted_tweets)
    })

@tweets_bp.route('/api/v1/tweets/pending-analysis', methods=['GET'])
@require_api_key
def analyze_pending_tweets():
    """Analyze pending tweets grouped by account"""
    conn = get_db()
    
    # Get pending tweets grouped by account
    pending_by_account = conn.execute('''
        SELECT 
            a.id as account_id,
            a.username,
            COUNT(t.id) as pending_count,
            MIN(t.created_at) as oldest_tweet,
            MAX(t.created_at) as newest_tweet
        FROM twitter_account a
        JOIN tweet t ON a.id = t.twitter_account_id
        WHERE t.status = 'pending'
        GROUP BY a.id, a.username
        ORDER BY pending_count DESC
    ''').fetchall()
    
    # Get total counts
    total_pending = conn.execute(
        "SELECT COUNT(*) as count FROM tweet WHERE status = 'pending'"
    ).fetchone()['count']
    
    total_accounts_with_pending = len(pending_by_account)
    
    # Get sample pending tweets
    sample_tweets = conn.execute('''
        SELECT t.id, t.content, a.username, t.created_at
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE t.status = 'pending'
        ORDER BY t.created_at DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'summary': {
            'total_pending': total_pending,
            'accounts_with_pending': total_accounts_with_pending
        },
        'by_account': [dict(row) for row in pending_by_account],
        'sample_tweets': [dict(tweet) for tweet in sample_tweets]
    })

@tweets_bp.route('/api/v1/tweet/post/<int:tweet_id>', methods=['POST'])
@require_api_key
def post_tweet(tweet_id):
    """Post a specific tweet to Twitter"""
    conn = get_db()
    
    # Get tweet details
    tweet = conn.execute(
        'SELECT * FROM tweet WHERE id = ?',
        (tweet_id,)
    ).fetchone()
    
    if not tweet:
        conn.close()
        return jsonify({'error': 'Tweet not found'}), 404
    
    if tweet['status'] == 'posted':
        conn.close()
        return jsonify({'error': 'Tweet already posted'}), 400
    
    # Post to Twitter
    success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
    
    if success:
        # Update tweet status
        conn.execute('''
            UPDATE tweet 
            SET status = 'posted', 
                twitter_id = ?,
                posted_at = ?
            WHERE id = ?
        ''', (result, datetime.now(UTC).isoformat(), tweet_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Tweet posted successfully',
            'twitter_id': result
        })
    else:
        # Update tweet status to failed
        conn.execute('''
            UPDATE tweet 
            SET status = 'failed'
            WHERE id = ?
        ''', (tweet_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'error': 'Failed to post tweet',
            'details': result
        }), 400

@tweets_bp.route('/api/v1/tweets/post-pending', methods=['POST'])
@require_api_key
def post_pending_tweets():
    """Post all pending tweets"""
    conn = get_db()
    
    # Get optional parameters
    data = request.get_json() or {}
    limit = data.get('limit', 50)
    account_id = data.get('account_id')
    
    # Build query for pending tweets
    query = '''
        SELECT t.*, a.username 
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE t.status = 'pending'
        AND t.thread_id IS NULL
    '''
    params = []
    
    if account_id:
        query += ' AND t.twitter_account_id = ?'
        params.append(account_id)
    
    query += ' ORDER BY t.created_at ASC LIMIT ?'
    params.append(limit)
    
    pending_tweets = conn.execute(query, params).fetchall()
    
    results = {
        'posted': [],
        'failed': [],
        'rate_limited': []
    }
    
    for tweet in pending_tweets:
        # Check rate limit
        delay = get_rate_limit_delay(tweet['twitter_account_id'])
        if delay > 0:
            results['rate_limited'].append({
                'tweet_id': tweet['id'],
                'account': tweet['username'],
                'wait_seconds': delay
            })
            continue
        
        # Post tweet
        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
        
        if success:
            # Update tweet status
            conn.execute('''
                UPDATE tweet 
                SET status = 'posted', 
                    twitter_id = ?,
                    posted_at = ?
                WHERE id = ?
            ''', (result, datetime.now(UTC).isoformat(), tweet['id']))
            
            results['posted'].append({
                'tweet_id': tweet['id'],
                'twitter_id': result,
                'account': tweet['username']
            })
        else:
            # Update tweet status to failed
            conn.execute('''
                UPDATE tweet 
                SET status = 'failed'
                WHERE id = ?
            ''', (tweet['id'],))
            
            results['failed'].append({
                'tweet_id': tweet['id'],
                'account': tweet['username'],
                'error': result
            })
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'summary': {
            'posted': len(results['posted']),
            'failed': len(results['failed']),
            'rate_limited': len(results['rate_limited'])
        },
        'details': results
    })

def post_tweets_background(job_id, batch_size=10, account_id=None):
    """Background function to post tweets"""
    conn = get_db()
    
    # Initialize job status
    background_jobs[job_id] = {
        'status': 'running',
        'posted': 0,
        'failed': 0,
        'rate_limited': 0,
        'started_at': datetime.now(UTC).isoformat()
    }
    
    try:
        # Build query for pending tweets
        query = '''
            SELECT t.*, a.username 
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.status = 'pending'
            AND t.thread_id IS NULL
        '''
        params = []
        
        if account_id:
            query += ' AND t.twitter_account_id = ?'
            params.append(account_id)
        
        query += ' ORDER BY t.created_at ASC'
        
        pending_tweets = conn.execute(query, params).fetchall()
        
        for i, tweet in enumerate(pending_tweets):
            if i >= batch_size:
                break
            
            # Check rate limit
            delay = get_rate_limit_delay(tweet['twitter_account_id'])
            if delay > 0:
                background_jobs[job_id]['rate_limited'] += 1
                continue
            
            # Post tweet
            success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
            
            if success:
                # Update tweet status
                conn.execute('''
                    UPDATE tweet 
                    SET status = 'posted', 
                        twitter_id = ?,
                        posted_at = ?
                    WHERE id = ?
                ''', (result, datetime.now(UTC).isoformat(), tweet['id']))
                
                background_jobs[job_id]['posted'] += 1
            else:
                # Update tweet status to failed
                conn.execute('''
                    UPDATE tweet 
                    SET status = 'failed'
                    WHERE id = ?
                ''', (tweet['id'],))
                
                background_jobs[job_id]['failed'] += 1
        
        conn.commit()
        background_jobs[job_id]['status'] = 'completed'
        background_jobs[job_id]['completed_at'] = datetime.now(UTC).isoformat()
        
    except Exception as e:
        background_jobs[job_id]['status'] = 'failed'
        background_jobs[job_id]['error'] = str(e)
    finally:
        conn.close()

@tweets_bp.route('/api/v1/tweets/post-pending-async', methods=['POST'])
@require_api_key
def post_pending_tweets_async():
    """Post pending tweets asynchronously"""
    data = request.get_json() or {}
    batch_size = data.get('batch_size', 10)
    account_id = data.get('account_id')
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Start background thread
    thread = threading.Thread(
        target=post_tweets_background,
        args=(job_id, batch_size, account_id)
    )
    thread.start()
    
    return jsonify({
        'message': 'Background job started',
        'job_id': job_id,
        'check_status_url': f'/api/v1/jobs/{job_id}'
    }), 202

@tweets_bp.route('/api/v1/jobs/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    """Get status of a background job"""
    if job_id not in background_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(background_jobs[job_id])

@tweets_bp.route('/api/v1/tweet/retry/<int:tweet_id>', methods=['POST'])
@require_api_key
def retry_failed_tweet(tweet_id):
    """Retry a failed tweet"""
    conn = get_db()
    
    # Get tweet details
    tweet = conn.execute(
        'SELECT * FROM tweet WHERE id = ? AND status = "failed"',
        (tweet_id,)
    ).fetchone()
    
    if not tweet:
        conn.close()
        return jsonify({'error': 'Failed tweet not found'}), 404
    
    # Reset status to pending
    conn.execute(
        'UPDATE tweet SET status = "pending" WHERE id = ?',
        (tweet_id,)
    )
    conn.commit()
    
    # Try posting again
    success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
    
    if success:
        conn.execute('''
            UPDATE tweet 
            SET status = 'posted', 
                twitter_id = ?,
                posted_at = ?
            WHERE id = ?
        ''', (result, datetime.now(UTC).isoformat(), tweet_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Tweet posted successfully',
            'twitter_id': result
        })
    else:
        conn.execute(
            'UPDATE tweet SET status = "failed" WHERE id = ?',
            (tweet_id,)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'error': 'Failed to post tweet',
            'details': result
        }), 400

@tweets_bp.route('/api/v1/tweets/retry-failed', methods=['POST'])
@require_api_key
def retry_all_failed_tweets():
    """Retry failed tweets with batching and rate limiting"""
    import time
    
    data = request.get_json() or {}
    max_tweets = data.get('max_tweets', 10)  # Limit to prevent timeout
    delay_between_tweets = data.get('delay_between_tweets', 2)  # Rate limiting
    account_id = data.get('account_id')  # Optional: filter by account
    
    conn = get_db()
    
    # Build query to get failed tweets
    query = '''
        SELECT t.*, a.username 
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE t.status = 'failed'
        AND a.status = 'active'
    '''
    params = []
    
    if account_id:
        query += ' AND t.twitter_account_id = ?'
        params.append(account_id)
    
    query += ' ORDER BY t.created_at ASC LIMIT ?'
    params.append(max_tweets)
    
    failed_tweets = conn.execute(query, params).fetchall()
    
    if not failed_tweets:
        conn.close()
        return jsonify({
            'message': 'No failed tweets found to retry',
            'summary': {
                'total_attempted': 0,
                'posted': 0,
                'still_failed': 0,
                'skipped_inactive_accounts': 0
            }
        })
    
    results = {
        'posted': [],
        'still_failed': [],
        'skipped_rate_limit': []
    }
    
    for i, tweet in enumerate(failed_tweets):
        # Check rate limit for this account
        from app.utils.rate_limit import get_rate_limit_status
        rate_status = get_rate_limit_status(tweet['twitter_account_id'])
        
        if rate_status['tweets_posted'] >= rate_status['limit']:
            results['skipped_rate_limit'].append({
                'tweet_id': tweet['id'],
                'account': tweet['username'],
                'reason': f"Rate limit exceeded ({rate_status['tweets_posted']}/{rate_status['limit']})"
            })
            continue
        
        # Reset to pending and commit immediately to avoid locks
        conn.execute(
            'UPDATE tweet SET status = "pending" WHERE id = ?',
            (tweet['id'],)
        )
        conn.commit()
        
        # Close connection before making API call to prevent database locks
        conn.close()
        
        # Make API call with fresh connection
        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
        
        # Reopen connection for database updates
        conn = get_db()
        
        if success:
            conn.execute('''
                UPDATE tweet 
                SET status = 'posted', 
                    twitter_id = ?,
                    posted_at = ?
                WHERE id = ?
            ''', (result, datetime.now(UTC).isoformat(), tweet['id']))
            
            results['posted'].append({
                'tweet_id': tweet['id'],
                'twitter_id': result,
                'account': tweet['username']
            })
        else:
            conn.execute(
                'UPDATE tweet SET status = "failed" WHERE id = ?',
                (tweet['id'],)
            )
            
            results['still_failed'].append({
                'tweet_id': tweet['id'],
                'account': tweet['username'],
                'error': result
            })
        
        conn.commit()
        
        # Add delay between tweets to respect rate limits
        if delay_between_tweets > 0 and i < len(failed_tweets) - 1:
            time.sleep(delay_between_tweets)
    
    # Final connection cleanup (conn is already managed per iteration)
    if 'conn' in locals() and conn:
        conn.close()
    
    return jsonify({
        'message': f'Processed {len(failed_tweets)} failed tweets',
        'summary': {
            'total_attempted': len(failed_tweets),
            'posted': len(results['posted']),
            'still_failed': len(results['still_failed']),
            'skipped_rate_limit': len(results['skipped_rate_limit'])
        },
        'details': results,
        'config': {
            'max_tweets': max_tweets,
            'delay_between_tweets': delay_between_tweets,
            'account_filter': account_id
        }
    })

@tweets_bp.route('/api/v1/tweets/reset-failed', methods=['POST'])
@require_api_key
def reset_failed_tweets():
    """Reset failed tweets to pending status"""
    conn = get_db()
    
    # Count failed tweets
    count = conn.execute(
        'SELECT COUNT(*) as count FROM tweet WHERE status = "failed"'
    ).fetchone()['count']
    
    # Reset all failed tweets to pending
    conn.execute('UPDATE tweet SET status = "pending" WHERE status = "failed"')
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Reset {count} failed tweets to pending status',
        'count': count
    })

@tweets_bp.route('/api/v1/tweets/cleanup', methods=['POST'])
@require_api_key
def cleanup_tweets():
    """Clean up old tweets"""
    data = request.get_json() or {}
    days_old = data.get('days_old', 30)
    
    # Handle both 'status' (single) and 'statuses' (array) parameters
    statuses = data.get('statuses', [])
    if not statuses:
        status = data.get('status', 'posted')
        statuses = [status]
    
    account_id = data.get('account_id')
    
    conn = get_db()
    
    # Build query conditions
    conditions = []
    params = []
    
    # Status condition
    if len(statuses) == 1:
        conditions.append('status = ?')
        params.append(statuses[0])
    else:
        status_placeholders = ','.join(['?' for _ in statuses])
        conditions.append(f'status IN ({status_placeholders})')
        params.extend(statuses)
    
    # Date condition
    conditions.append("datetime(created_at) < datetime('now', '-' || ? || ' days')")
    params.append(days_old)
    
    # Account condition
    if account_id:
        conditions.append('twitter_account_id = ?')
        params.append(account_id)
    
    where_clause = ' AND '.join(conditions)
    
    # Count tweets to delete
    count_query = f'SELECT COUNT(*) as count FROM tweet WHERE {where_clause}'
    count = conn.execute(count_query, params).fetchone()['count']
    
    # Delete old tweets
    delete_query = f'DELETE FROM tweet WHERE {where_clause}'
    conn.execute(delete_query, params)
    
    conn.commit()
    conn.close()
    
    status_text = ', '.join(statuses) if len(statuses) > 1 else statuses[0]
    account_text = f' from account {account_id}' if account_id else ''
    
    return jsonify({
        'message': f'Deleted {count} {status_text} tweets older than {days_old} days{account_text}',
        'count': count,
        'statuses': statuses,
        'days_old': days_old,
        'account_id': account_id
    })

@tweets_bp.route('/api/v1/tweets/<int:tweet_id>', methods=['DELETE'])
@require_api_key
def delete_tweet(tweet_id):
    """Delete a specific tweet"""
    conn = get_db()
    
    # Check if tweet exists
    tweet = conn.execute(
        'SELECT * FROM tweet WHERE id = ?',
        (tweet_id,)
    ).fetchone()
    
    if not tweet:
        conn.close()
        return jsonify({'error': 'Tweet not found'}), 404
    
    # Delete tweet
    conn.execute('DELETE FROM tweet WHERE id = ?', (tweet_id,))
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': 'Tweet deleted successfully',
        'tweet_id': tweet_id
    })

@tweets_bp.route('/api/v1/accounts/<int:account_id>/tweets/cleanup', methods=['DELETE'])
@require_api_key
def cleanup_account_tweets(account_id):
    """Delete all tweets from a specific account"""
    data = request.get_json() or {}
    
    # Optional filters
    statuses = data.get('statuses', [])  # Filter by specific statuses (optional)
    days_old = data.get('days_old')      # Filter by age (optional)
    confirm = data.get('confirm', False) # Safety confirmation required
    
    if not confirm:
        return jsonify({
            'error': 'This operation will delete tweets permanently. Set "confirm": true to proceed.'
        }), 400
    
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
        
        # Build query conditions
        conditions = ['twitter_account_id = ?']
        params = [account_id]
        
        if statuses:
            # Filter by specific statuses
            status_placeholders = ','.join(['?' for _ in statuses])
            conditions.append(f'status IN ({status_placeholders})')
            params.extend(statuses)
        
        if days_old:
            # Filter by age
            conditions.append("created_at < datetime('now', ? || ' days')")
            params.append(-days_old)
        
        where_clause = ' AND '.join(conditions)
        
        # Count tweets to delete
        count_query = f'SELECT COUNT(*) as count FROM tweet WHERE {where_clause}'
        count = conn.execute(count_query, params).fetchone()['count']
        
        if count == 0:
            conn.close()
            return jsonify({
                'message': 'No tweets found matching the criteria',
                'count': 0,
                'account_username': account['username']
            })
        
        # Get breakdown by status before deletion
        breakdown_query = f'''
            SELECT status, COUNT(*) as count 
            FROM tweet 
            WHERE {where_clause} 
            GROUP BY status
        '''
        breakdown = conn.execute(breakdown_query, params).fetchall()
        status_breakdown = {row['status']: row['count'] for row in breakdown}
        
        # Delete tweets
        delete_query = f'DELETE FROM tweet WHERE {where_clause}'
        conn.execute(delete_query, params)
        conn.commit()
        conn.close()
        
        # Build filter description
        filter_desc = []
        if statuses:
            filter_desc.append(f"status: {', '.join(statuses)}")
        if days_old:
            filter_desc.append(f"older than {days_old} days")
        
        filter_text = f" ({', '.join(filter_desc)})" if filter_desc else ""
        
        return jsonify({
            'message': f'Deleted {count} tweets from account @{account["username"]}{filter_text}',
            'count': count,
            'account_id': account_id,
            'account_username': account['username'],
            'status_breakdown': status_breakdown,
            'filters_applied': {
                'statuses': statuses or 'all',
                'days_old': days_old or 'all'
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@tweets_bp.route('/api/v1/accounts/<int:account_id>/tweets/delete-from-twitter', methods=['POST'])
@require_api_key
def bulk_delete_from_twitter(account_id):
    """Delete tweets from Twitter (X) using the official API"""
    data = request.get_json() or {}
    
    # Parameters
    limit = data.get('limit', 10)  # How many tweets to delete
    include_threads = data.get('include_threads', True)  # Whether to delete complete threads
    tweet_ids = data.get('tweet_ids', [])  # Specific tweet IDs to delete
    confirm = data.get('confirm', False)  # Safety confirmation
    
    # Validation
    if not confirm:
        return jsonify({
            'error': 'This will permanently delete tweets from X/Twitter. Set "confirm": true to proceed.',
            'warning': 'Deleted tweets cannot be recovered'
        }), 400
    
    if limit > 50:
        return jsonify({'error': 'Maximum 50 tweets can be deleted at once due to rate limits'}), 400
    
    try:
        conn = get_db()
        
        # Verify account exists
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        results = {
            'deleted_from_twitter': [],
            'failed_to_delete': [],
            'rate_limited': [],
            'already_deleted': [],
            'threads_deleted': {}
        }
        
        # Get tweets to delete
        if tweet_ids:
            # Delete specific tweet IDs
            placeholders = ','.join(['?' for _ in tweet_ids])
            query = f'''
                SELECT t.*, a.username 
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.twitter_account_id = ? AND t.id IN ({placeholders})
                AND t.twitter_id IS NOT NULL 
                AND t.twitter_id NOT LIKE 'mock_%'
            '''
            params = [account_id] + tweet_ids
        else:
            # Delete most recent tweets with twitter_id (posted tweets)
            query = '''
                SELECT t.*, a.username 
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.twitter_account_id = ? 
                AND t.twitter_id IS NOT NULL
                AND t.twitter_id NOT LIKE 'mock_%'
                ORDER BY t.posted_at DESC
                LIMIT ?
            '''
            params = [account_id, limit]
        
        tweets_to_delete = conn.execute(query, params).fetchall()
        
        if not tweets_to_delete:
            conn.close()
            return jsonify({
                'message': 'No posted tweets found to delete',
                'account_username': account['username'],
                'results': results
            })
        
        # Group by threads if include_threads is enabled
        if include_threads:
            thread_groups = {}
            standalone_tweets = []
            
            for tweet in tweets_to_delete:
                if tweet['thread_id']:
                    thread_id = tweet['thread_id']
                    if thread_id not in thread_groups:
                        thread_groups[thread_id] = []
                    thread_groups[thread_id].append(tweet)
                else:
                    standalone_tweets.append(tweet)
            
            # For each thread, get ALL tweets in the thread
            for thread_id in thread_groups.keys():
                thread_tweets = conn.execute('''
                    SELECT t.*, a.username 
                    FROM tweet t
                    JOIN twitter_account a ON t.twitter_account_id = a.id
                    WHERE t.thread_id = ? AND t.twitter_id IS NOT NULL
                    AND t.twitter_id NOT LIKE 'mock_%'
                    ORDER BY t.thread_position ASC
                ''', (thread_id,)).fetchall()
                thread_groups[thread_id] = thread_tweets
            
            # Process threads first (delete in reverse order - last tweet first)
            for thread_id, thread_tweets in thread_groups.items():
                thread_results = {
                    'deleted': [],
                    'failed': [],
                    'total_tweets': len(thread_tweets)
                }
                
                # Delete in reverse order (newest first)
                for tweet in reversed(thread_tweets):
                    # Check rate limit
                    delay = get_rate_limit_delay(account_id)
                    if delay > 0:
                        results['rate_limited'].append({
                            'tweet_id': tweet['id'],
                            'twitter_id': tweet['twitter_id'],
                            'wait_seconds': delay
                        })
                        continue
                    
                    # Attempt deletion from Twitter
                    success, message = delete_from_twitter(account_id, tweet['twitter_id'])
                    
                    if success:
                        # Mark as deleted in local DB
                        conn.execute('''
                            UPDATE tweet 
                            SET status = 'deleted_from_twitter'
                            WHERE id = ?
                        ''', (tweet['id'],))
                        
                        thread_results['deleted'].append({
                            'tweet_id': tweet['id'],
                            'twitter_id': tweet['twitter_id'],
                            'content_preview': tweet['content'][:50] + '...' if len(tweet['content']) > 50 else tweet['content']
                        })
                        results['deleted_from_twitter'].append({
                            'tweet_id': tweet['id'],
                            'twitter_id': tweet['twitter_id'],
                            'thread_id': thread_id
                        })
                    else:
                        thread_results['failed'].append({
                            'tweet_id': tweet['id'],
                            'twitter_id': tweet['twitter_id'],
                            'error': message
                        })
                        
                        if "not found" in message.lower():
                            results['already_deleted'].append({
                                'tweet_id': tweet['id'],
                                'twitter_id': tweet['twitter_id']
                            })
                        else:
                            results['failed_to_delete'].append({
                                'tweet_id': tweet['id'],
                                'twitter_id': tweet['twitter_id'],
                                'error': message
                            })
                
                results['threads_deleted'][thread_id] = thread_results
            
            # Process standalone tweets
            tweets_to_process = standalone_tweets
        else:
            tweets_to_process = tweets_to_delete
        
        # Process individual tweets or standalone tweets
        for tweet in tweets_to_process:
            # Check rate limit
            delay = get_rate_limit_delay(account_id)
            if delay > 0:
                results['rate_limited'].append({
                    'tweet_id': tweet['id'],
                    'twitter_id': tweet['twitter_id'],
                    'wait_seconds': delay
                })
                continue
            
            # Attempt deletion from Twitter
            success, message = delete_from_twitter(account_id, tweet['twitter_id'])
            
            if success:
                # Mark as deleted in local DB
                conn.execute('''
                    UPDATE tweet 
                    SET status = 'deleted_from_twitter'
                    WHERE id = ?
                ''', (tweet['id'],))
                
                results['deleted_from_twitter'].append({
                    'tweet_id': tweet['id'],
                    'twitter_id': tweet['twitter_id'],
                    'content_preview': tweet['content'][:50] + '...' if len(tweet['content']) > 50 else tweet['content']
                })
            else:
                if "not found" in message.lower():
                    results['already_deleted'].append({
                        'tweet_id': tweet['id'],
                        'twitter_id': tweet['twitter_id']
                    })
                else:
                    results['failed_to_delete'].append({
                        'tweet_id': tweet['id'],
                        'twitter_id': tweet['twitter_id'],
                        'error': message
                    })
        
        conn.commit()
        conn.close()
        
        # Summary
        total_deleted = len(results['deleted_from_twitter'])
        total_failed = len(results['failed_to_delete'])
        total_rate_limited = len(results['rate_limited'])
        total_already_deleted = len(results['already_deleted'])
        
        return jsonify({
            'message': f'Bulk delete completed for @{account["username"]}',
            'summary': {
                'total_processed': total_deleted + total_failed + total_rate_limited + total_already_deleted,
                'successfully_deleted': total_deleted,
                'failed_to_delete': total_failed,
                'rate_limited': total_rate_limited,
                'already_deleted': total_already_deleted,
                'threads_processed': len(results['threads_deleted'])
            },
            'account_id': account_id,
            'account_username': account['username'],
            'results': results,
            'rate_limit_info': {
                'message': 'X API has rate limits. If many requests are rate limited, wait 15 minutes and try again.',
                'current_delay': get_rate_limit_delay(account_id)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500