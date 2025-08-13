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
from app.services.twitter import post_to_twitter
from app.utils.rate_limit import get_rate_limit_delay

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

@tweets_bp.route('/api/v1/tweets', methods=['GET'])
@require_api_key
def get_tweets():
    """Get all tweets with optional filters"""
    conn = get_db()
    
    # Get query parameters
    status = request.args.get('status')
    account_id = request.args.get('account_id')
    limit = request.args.get('limit', 100, type=int)
    
    # Build query
    query = '''
        SELECT t.*, a.username 
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE 1=1
    '''
    params = []
    
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
            'reply_to_tweet_id': tweet['reply_to_tweet_id']
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
    """Retry all failed tweets"""
    conn = get_db()
    
    # Get all failed tweets
    failed_tweets = conn.execute('''
        SELECT t.*, a.username 
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE t.status = 'failed'
        ORDER BY t.created_at ASC
    ''').fetchall()
    
    results = {
        'posted': [],
        'still_failed': []
    }
    
    for tweet in failed_tweets:
        # Reset to pending and try posting
        conn.execute(
            'UPDATE tweet SET status = "pending" WHERE id = ?',
            (tweet['id'],)
        )
        
        success, result = post_to_twitter(tweet['twitter_account_id'], tweet['content'])
        
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
    conn.close()
    
    return jsonify({
        'summary': {
            'total_attempted': len(failed_tweets),
            'posted': len(results['posted']),
            'still_failed': len(results['still_failed'])
        },
        'details': results
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
    status = data.get('status', 'posted')
    
    conn = get_db()
    
    # Count tweets to delete
    count = conn.execute('''
        SELECT COUNT(*) as count 
        FROM tweet 
        WHERE status = ? 
        AND created_at < datetime('now', ? || ' days')
    ''', (status, -days_old)).fetchone()['count']
    
    # Delete old tweets
    conn.execute('''
        DELETE FROM tweet 
        WHERE status = ? 
        AND created_at < datetime('now', ? || ' days')
    ''', (status, -days_old))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Deleted {count} {status} tweets older than {days_old} days',
        'count': count
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