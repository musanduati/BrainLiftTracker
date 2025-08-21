from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import uuid
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key
from app.services.twitter import post_to_twitter
from app.utils.dok_parser import parse_dok_metadata

threads_bp = Blueprint('threads', __name__)

@threads_bp.route('/api/v1/thread', methods=['POST'])
@require_api_key
def create_thread():
    """Create a Twitter thread (multiple connected tweets)"""
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
        
        # Parse DOK metadata from first tweet
        dok_type, change_type = parse_dok_metadata(tweets[0]) if tweets else (None, None)
        
        # Create all tweets in the thread as pending
        created_tweets = []
        for i, tweet_text in enumerate(tweets):
            cursor = conn.execute(
                '''INSERT INTO tweet (twitter_account_id, content, thread_id, thread_position, status, dok_type, change_type) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (account_id, tweet_text, thread_id, i, 'pending', dok_type, change_type)
            )
            tweet_id = cursor.lastrowid
            created_tweets.append({
                'id': tweet_id,
                'position': i,
                'content': tweet_text
            })
        
        conn.commit()
        conn.close()
        
        result = {
            'message': f'Thread created with {len(tweets)} tweets',
            'thread_id': thread_id,
            'tweets': created_tweets
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

@threads_bp.route('/api/v1/thread/post/<thread_id>', methods=['POST'])
@require_api_key
def post_thread(thread_id):
    """Post all tweets in a thread to Twitter"""
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
                    ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
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

@threads_bp.route('/api/v1/threads', methods=['GET'])
@require_api_key
def get_threads():
    """Get all threads"""
    try:
        conn = get_db()
        
        # Get unique threads with their tweet count
        threads = conn.execute('''
            SELECT 
                t.thread_id,
                t.twitter_account_id,
                COUNT(*) as tweet_count,
                MIN(t.created_at) as created_at,
                SUM(CASE WHEN t.status = 'posted' THEN 1 ELSE 0 END) as posted_count,
                SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.thread_id IS NOT NULL
            AND a.username NOT IN ('BrainLift WF-X Integration', 'klair_three')
            GROUP BY t.thread_id, t.twitter_account_id
            ORDER BY t.created_at DESC
        ''').fetchall()
        
        result = []
        for thread in threads:
            # Get account username
            account = conn.execute(
                'SELECT username FROM twitter_account WHERE id = ?',
                (thread['twitter_account_id'],)
            ).fetchone()
            
            result.append({
                'thread_id': thread['thread_id'],
                'account_id': thread['twitter_account_id'],
                'account_username': account['username'] if account else 'Unknown',  # Fixed: Changed from 'username' to 'account_username'
                'tweet_count': thread['tweet_count'],
                'posted_count': thread['posted_count'],
                'pending_count': thread['pending_count'],
                'failed_count': thread['failed_count'],
                'created_at': thread['created_at']
            })
        
        conn.close()
        
        return jsonify({
            'threads': result,
            'count': len(result)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/thread/<thread_id>', methods=['GET'])
@require_api_key
def get_thread(thread_id):
    """Get details of a specific thread"""
    try:
        conn = get_db()
        
        # Get tweets in the thread
        tweets = conn.execute(
            '''SELECT id, content, status, thread_position, twitter_id, posted_at, reply_to_tweet_id 
               FROM tweet 
               WHERE thread_id = ?
               ORDER BY thread_position''',
            (thread_id,)
        ).fetchall()
        
        if not tweets:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        # Get account info
        account_id = conn.execute(
            'SELECT twitter_account_id FROM tweet WHERE thread_id = ? LIMIT 1',
            (thread_id,)
        ).fetchone()['twitter_account_id']
        
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        conn.close()
        
        return jsonify({
            'thread_id': thread_id,
            'account_id': account_id,
            'username': account['username'] if account else 'Unknown',
            'tweets': [dict(tweet) for tweet in tweets],
            'tweet_count': len(tweets)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/thread/<thread_id>/debug', methods=['GET'])
@require_api_key
def debug_thread(thread_id):
    """Debug information for a thread"""
    try:
        conn = get_db()
        
        # Get all tweets in thread with full details
        tweets = conn.execute(
            '''SELECT * FROM tweet WHERE thread_id = ? ORDER BY thread_position''',
            (thread_id,)
        ).fetchall()
        
        if not tweets:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        conn.close()
        
        return jsonify({
            'thread_id': thread_id,
            'tweet_count': len(tweets),
            'tweets': [dict(tweet) for tweet in tweets]
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/thread/<thread_id>', methods=['DELETE'])
@require_api_key
def delete_thread(thread_id):
    """Delete a thread and all its tweets"""
    try:
        conn = get_db()
        
        # Check if thread exists
        tweet_count = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE thread_id = ?',
            (thread_id,)
        ).fetchone()['count']
        
        if tweet_count == 0:
            conn.close()
            return jsonify({'error': 'Thread not found'}), 404
        
        # Delete all tweets in thread
        conn.execute('DELETE FROM tweet WHERE thread_id = ?', (thread_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Thread deleted successfully',
            'thread_id': thread_id,
            'tweets_deleted': tweet_count
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/thread/retry/<thread_id>', methods=['POST'])
@require_api_key
def retry_failed_thread(thread_id):
    """Retry posting a failed thread"""
    try:
        conn = get_db()
        
        # Reset failed tweets to pending
        conn.execute(
            '''UPDATE tweet 
               SET status = 'pending', twitter_id = NULL, posted_at = NULL, reply_to_tweet_id = NULL
               WHERE thread_id = ? AND status = 'failed' ''',
            (thread_id,)
        )
        conn.commit()
        
        # Check if we have pending tweets now
        pending_count = conn.execute(
            '''SELECT COUNT(*) as count 
               FROM tweet 
               WHERE thread_id = ? AND status = 'pending' ''',
            (thread_id,)
        ).fetchone()['count']
        
        conn.close()
        
        if pending_count == 0:
            return jsonify({'error': 'No failed tweets to retry in this thread'}), 404
        
        # Now post the thread
        return post_thread(thread_id)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/reset-failed', methods=['POST'])
@require_api_key
def reset_failed_threads():
    """Reset all failed threads to pending status"""
    try:
        conn = get_db()
        
        # Find threads with failed tweets
        failed_threads = conn.execute('''
            SELECT DISTINCT thread_id 
            FROM tweet 
            WHERE thread_id IS NOT NULL AND status = 'failed'
        ''').fetchall()
        
        reset_count = 0
        for thread in failed_threads:
            # Reset failed tweets to pending for each thread
            conn.execute(
                '''UPDATE tweet 
                   SET status = 'pending', twitter_id = NULL, posted_at = NULL, reply_to_tweet_id = NULL
                   WHERE thread_id = ? AND status = 'failed' ''',
                (thread['thread_id'],)
            )
            reset_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Reset {reset_count} failed threads to pending',
            'thread_count': reset_count,
            'thread_ids': [t['thread_id'] for t in failed_threads]
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/cleanup', methods=['POST'])
@require_api_key
def cleanup_threads():
    """Clean up old threads"""
    try:
        data = request.get_json() or {}
        days_old = data.get('days_old', 30)
        status = data.get('status', 'posted')
        
        conn = get_db()
        
        # Find threads to delete
        threads_to_delete = conn.execute('''
            SELECT DISTINCT thread_id, COUNT(*) as tweet_count
            FROM tweet 
            WHERE thread_id IS NOT NULL 
            AND status = ?
            AND created_at < datetime('now', ? || ' days')
            GROUP BY thread_id
        ''', (status, -days_old)).fetchall()
        
        total_tweets_deleted = 0
        for thread in threads_to_delete:
            conn.execute('DELETE FROM tweet WHERE thread_id = ?', (thread['thread_id'],))
            total_tweets_deleted += thread['tweet_count']
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Deleted {len(threads_to_delete)} threads ({total_tweets_deleted} tweets) older than {days_old} days',
            'threads_deleted': len(threads_to_delete),
            'tweets_deleted': total_tweets_deleted
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/post-all-pending', methods=['POST'])
@require_api_key
def post_all_pending_threads():
    """Post all pending threads to X with rate limiting"""
    try:
        data = request.get_json() or {}
        account_id = data.get('account_id')
        max_threads = data.get('max_threads', 10)  # Limit threads to avoid overwhelming
        delay_between_threads = data.get('delay_between_threads', 5)  # Seconds between threads
        
        conn = get_db()
        
        # Get all pending threads, optionally filtered by account
        if account_id:
            # Verify account exists
            account = conn.execute(
                'SELECT * FROM twitter_account WHERE id = ?', 
                (account_id,)
            ).fetchone()
            
            if not account:
                conn.close()
                return jsonify({'error': 'Account not found'}), 404
                
            pending_threads_query = '''
                SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                       COUNT(*) as tweet_count
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.thread_id IS NOT NULL 
                AND t.status = 'pending' 
                AND t.twitter_account_id = ?
                AND a.status != 'deleted'
                GROUP BY t.thread_id, t.twitter_account_id
                ORDER BY created_at ASC
                LIMIT ?
            '''
            pending_threads = conn.execute(pending_threads_query, (account_id, max_threads)).fetchall()
        else:
            # Get pending threads for all accounts
            pending_threads_query = '''
                SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                       COUNT(*) as tweet_count
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.thread_id IS NOT NULL 
                AND t.status = 'pending'
                AND a.status != 'deleted'
                GROUP BY t.thread_id, t.twitter_account_id
                ORDER BY created_at ASC
                LIMIT ?
            '''
            pending_threads = conn.execute(pending_threads_query, (max_threads,)).fetchall()
        
        if not pending_threads:
            conn.close()
            return jsonify({
                'message': 'No pending threads found',
                'posted': 0,
                'failed': 0,
                'threads': []
            })
        
        results = []
        total_posted = 0
        total_failed = 0
        
        for thread in pending_threads:
            thread_id = thread['thread_id']
            thread_account_id = thread['twitter_account_id']
            
            # Check rate limit for this account before proceeding
            from app.utils.rate_limit import get_rate_limit_status
            rate_status = get_rate_limit_status(thread_account_id)
            
            if rate_status['tweets_posted'] + thread['tweet_count'] > rate_status['limit']:
                # Would exceed rate limit, skip this thread
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'skipped',
                    'reason': f"Would exceed rate limit ({rate_status['tweets_posted']}/{rate_status['limit']})",
                    'tweet_count': thread['tweet_count']
                })
                continue
            
            # Get tweets for this thread
            tweets = conn.execute(
                '''SELECT id, twitter_account_id, content, thread_position 
                   FROM tweet 
                   WHERE thread_id = ? AND status = 'pending'
                   ORDER BY thread_position''',
                (thread_id,)
            ).fetchall()
            
            if not tweets:
                continue
            
            # Post the thread
            posted_tweets = []
            failed_tweets = []
            previous_tweet_id = None
            
            for tweet in tweets:
                success, result = post_to_twitter(
                    tweet['twitter_account_id'], 
                    tweet['content'],
                    reply_to_tweet_id=previous_tweet_id
                )
                
                if success:
                    # Update tweet status
                    conn.execute(
                        '''UPDATE tweet 
                           SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                           WHERE id = ?''',
                        ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                    )
                    conn.commit()
                    
                    posted_tweets.append({
                        'tweet_id': tweet['id'],
                        'twitter_id': result,
                        'position': tweet['thread_position']
                    })
                    
                    previous_tweet_id = result
                else:
                    # Mark as failed and stop the thread
                    conn.execute(
                        'UPDATE tweet SET status = ? WHERE id = ?',
                        ('failed', tweet['id'])
                    )
                    conn.commit()
                    
                    failed_tweets.append({
                        'tweet_id': tweet['id'],
                        'position': tweet['thread_position'],
                        'error': result
                    })
                    break
            
            thread_result = {
                'thread_id': thread_id,
                'account_id': thread_account_id,
                'status': 'completed' if not failed_tweets else 'partial_failure',
                'posted_count': len(posted_tweets),
                'failed_count': len(failed_tweets),
                'tweets': {
                    'posted': posted_tweets,
                    'failed': failed_tweets
                }
            }
            
            results.append(thread_result)
            total_posted += len(posted_tweets)
            total_failed += len(failed_tweets)
            
            # Add delay between threads to respect rate limits
            if delay_between_threads > 0 and thread != pending_threads[-1]:
                import time
                time.sleep(delay_between_threads)
        
        conn.close()
        
        return jsonify({
            'message': f'Processed {len(pending_threads)} threads',
            'posted': total_posted,
            'failed': total_failed,
            'threads_processed': len(results),
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/delete-by-status', methods=['DELETE'])
@require_api_key
def delete_threads_by_status():
    """Delete all threads by status across all accounts for cleanup"""
    try:
        data = request.get_json() or {}
        status = data.get('status', 'failed')  # Default to 'failed', but can be 'pending', 'posted', etc.
        
        # Validate status
        valid_statuses = ['failed', 'pending', 'posted']
        if status not in valid_statuses:
            return jsonify({
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        conn = get_db()
        
        # Get threads with the specified status across all accounts
        threads_query = '''
            SELECT DISTINCT thread_id, twitter_account_id, COUNT(*) as tweet_count,
                   MIN(created_at) as created_at
            FROM tweet 
            WHERE thread_id IS NOT NULL 
            AND status = ?
            GROUP BY thread_id, twitter_account_id
        '''
        threads_to_delete = conn.execute(threads_query, (status,)).fetchall()
        
        if not threads_to_delete:
            conn.close()
            return jsonify({
                'message': f'No {status} threads found to delete',
                'status_filter': status,
                'threads_deleted': 0,
                'tweets_deleted': 0
            })
        
        # Delete all tweets in matching threads
        deleted_threads = []
        total_tweets_deleted = 0
        
        for thread in threads_to_delete:
            thread_id = thread['thread_id']
            tweet_count = thread['tweet_count']
            
            # Delete all tweets in this thread (entire thread gets deleted)
            conn.execute('DELETE FROM tweet WHERE thread_id = ?', (thread_id,))
            
            deleted_threads.append({
                'thread_id': thread_id,
                'account_id': thread['twitter_account_id'],
                'tweets_deleted': tweet_count,
                'created_at': thread['created_at']
            })
            
            total_tweets_deleted += tweet_count
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Successfully deleted {len(deleted_threads)} {status} threads ({total_tweets_deleted} tweets)',
            'status_filter': status,
            'threads_deleted': len(deleted_threads),
            'tweets_deleted': total_tweets_deleted,
            'deleted_threads': deleted_threads
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/retry-all-failed', methods=['POST'])
@require_api_key
def retry_all_failed_threads():
    """Retry posting all failed threads with rate limiting"""
    try:
        data = request.get_json() or {}
        account_id = data.get('account_id')  # Optional: filter by account
        max_threads = data.get('max_threads', 10)  # Limit threads to avoid overwhelming
        delay_between_threads = data.get('delay_between_threads', 5)  # Seconds between threads
        
        conn = get_db()
        
        # Build query to find threads with failed tweets
        if account_id:
            # Verify account exists
            account = conn.execute(
                'SELECT * FROM twitter_account WHERE id = ?', 
                (account_id,)
            ).fetchone()
            
            if not account:
                conn.close()
                return jsonify({'error': 'Account not found'}), 404
            
            # Get failed threads for specific account
            failed_threads_query = '''
                SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                       COUNT(*) as total_tweets,
                       SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_tweets,
                       SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_tweets
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.thread_id IS NOT NULL 
                AND t.twitter_account_id = ?
                AND a.status != 'deleted'
                AND t.thread_id IN (
                    SELECT DISTINCT thread_id 
                    FROM tweet 
                    WHERE status = 'failed' AND thread_id IS NOT NULL
                )
                GROUP BY t.thread_id, t.twitter_account_id
                ORDER BY created_at ASC
                LIMIT ?
            '''
            failed_threads = conn.execute(failed_threads_query, (account_id, max_threads)).fetchall()
        else:
            # Get failed threads across all accounts
            failed_threads_query = '''
                SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                       COUNT(*) as total_tweets,
                       SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_tweets,
                       SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_tweets
                FROM tweet t
                JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE t.thread_id IS NOT NULL 
                AND a.status != 'deleted'
                AND t.thread_id IN (
                    SELECT DISTINCT thread_id 
                    FROM tweet 
                    WHERE status = 'failed' AND thread_id IS NOT NULL
                )
                GROUP BY t.thread_id, t.twitter_account_id
                ORDER BY created_at ASC
                LIMIT ?
            '''
            failed_threads = conn.execute(failed_threads_query, (max_threads,)).fetchall()
        
        if not failed_threads:
            conn.close()
            return jsonify({
                'message': 'No failed threads found to retry',
                'retried': 0,
                'failed': 0,
                'threads': []
            })
        
        results = []
        total_retried = 0
        total_still_failed = 0
        
        for thread in failed_threads:
            thread_id = thread['thread_id']
            thread_account_id = thread['twitter_account_id']
            
            # Check rate limit for this account before proceeding
            from app.utils.rate_limit import get_rate_limit_status
            rate_status = get_rate_limit_status(thread_account_id)
            
            # Calculate how many tweets we might need to post (failed + pending)
            tweets_to_post = thread['failed_tweets'] + thread['pending_tweets']
            
            if rate_status['tweets_posted'] + tweets_to_post > rate_status['limit']:
                # Would exceed rate limit, skip this thread
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'skipped',
                    'reason': f"Would exceed rate limit ({rate_status['tweets_posted']}/{rate_status['limit']})",
                    'tweets_to_retry': tweets_to_post
                })
                continue
            
            # First, reset failed tweets to pending
            reset_result = conn.execute(
                '''UPDATE tweet 
                   SET status = 'pending', twitter_id = NULL, posted_at = NULL, reply_to_tweet_id = NULL
                   WHERE thread_id = ? AND status = 'failed' ''',
                (thread_id,)
            )
            reset_count = reset_result.rowcount
            conn.commit()
            
            if reset_count == 0:
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'no_failed_tweets',
                    'message': 'No failed tweets found to retry'
                })
                continue
            
            # Now get all pending tweets for this thread (including newly reset ones)
            tweets = conn.execute(
                '''SELECT id, twitter_account_id, content, thread_position 
                   FROM tweet 
                   WHERE thread_id = ? AND status = 'pending'
                   ORDER BY thread_position''',
                (thread_id,)
            ).fetchall()
            
            if not tweets:
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'no_pending_tweets',
                    'message': 'No pending tweets to post after reset'
                })
                continue
            
            # Find the last successfully posted tweet to continue the thread
            last_posted = conn.execute(
                '''SELECT twitter_id FROM tweet 
                   WHERE thread_id = ? AND status = 'posted'
                   ORDER BY thread_position DESC LIMIT 1''',
                (thread_id,)
            ).fetchone()
            
            previous_tweet_id = last_posted['twitter_id'] if last_posted else None
            
            # Post the remaining tweets
            posted_tweets = []
            failed_tweets = []
            
            for tweet in tweets:
                success, result = post_to_twitter(
                    tweet['twitter_account_id'], 
                    tweet['content'],
                    reply_to_tweet_id=previous_tweet_id
                )
                
                if success:
                    # Update tweet status
                    conn.execute(
                        '''UPDATE tweet 
                           SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                           WHERE id = ?''',
                        ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                    )
                    conn.commit()
                    
                    posted_tweets.append({
                        'tweet_id': tweet['id'],
                        'twitter_id': result,
                        'position': tweet['thread_position']
                    })
                    
                    previous_tweet_id = result
                else:
                    # Mark as failed and stop the thread
                    conn.execute(
                        'UPDATE tweet SET status = ? WHERE id = ?',
                        ('failed', tweet['id'])
                    )
                    conn.commit()
                    
                    failed_tweets.append({
                        'tweet_id': tweet['id'],
                        'position': tweet['thread_position'],
                        'error': result
                    })
                    break
            
            thread_result = {
                'thread_id': thread_id,
                'account_id': thread_account_id,
                'status': 'completed' if not failed_tweets else 'partial_failure',
                'reset_count': reset_count,
                'posted_count': len(posted_tweets),
                'failed_count': len(failed_tweets),
                'tweets': {
                    'posted': posted_tweets,
                    'failed': failed_tweets
                }
            }
            
            results.append(thread_result)
            total_retried += len(posted_tweets)
            total_still_failed += len(failed_tweets)
            
            # Add delay between threads to respect rate limits
            if delay_between_threads > 0 and thread != failed_threads[-1]:
                import time
                time.sleep(delay_between_threads)
        
        conn.close()
        
        return jsonify({
            'message': f'Processed {len(failed_threads)} failed threads',
            'retried': total_retried,
            'still_failed': total_still_failed,
            'threads_processed': len(results),
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/by-status/<status>', methods=['GET'])
@require_api_key
def get_threads_by_status(status):
    """Get threads filtered by status"""
    try:
        # Validate status
        valid_statuses = ['failed', 'pending', 'posted']
        if status not in valid_statuses:
            return jsonify({
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        conn = get_db()
        
        # Get threads with the specified status
        threads_query = '''
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
            AND thread_id IN (
                SELECT DISTINCT thread_id 
                FROM tweet 
                WHERE status = ? AND thread_id IS NOT NULL
            )
            GROUP BY thread_id, twitter_account_id
            ORDER BY created_at DESC
        '''
        threads = conn.execute(threads_query, (status,)).fetchall()
        
        result = []
        for thread in threads:
            # Get account username
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
        
        return jsonify({
            'status_filter': status,
            'threads': result,
            'count': len(result)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/v1/threads/automation/run', methods=['POST'])
@require_api_key
def run_thread_automation():
    """Automated thread posting service - combines pending posting and failed retry"""
    try:
        from datetime import datetime, timezone
        try:
            from datetime import UTC
        except ImportError:
            UTC = timezone.utc
        
        automation_start = datetime.now(UTC)
        data = request.get_json() or {}
        
        # Configuration parameters
        config = {
            'max_threads_per_run': data.get('max_threads_per_run', 10),
            'delay_between_threads': data.get('delay_between_threads', 5),
            'post_pending': data.get('post_pending', True),
            'retry_failed': data.get('retry_failed', True),
            'dry_run': data.get('dry_run', False)
        }
        
        automation_report = {
            'automation_id': f"auto_{int(automation_start.timestamp())}",
            'started_at': automation_start.isoformat(),
            'config': config,
            'results': {
                'pending_operation': None,
                'failed_retry_operation': None
            },
            'summary': {
                'total_threads_processed': 0,
                'total_tweets_posted': 0,
                'total_failures': 0,
                'operations_completed': 0,
                'rate_limit_skips': 0
            }
        }
        
        conn = get_db()
        
        # Check system status first
        total_pending = conn.execute(
            '''SELECT COUNT(DISTINCT thread_id) as count 
               FROM tweet 
               WHERE thread_id IS NOT NULL AND status = 'pending' '''
        ).fetchone()['count']
        
        total_failed_threads = conn.execute(
            '''SELECT COUNT(DISTINCT thread_id) as count 
               FROM tweet 
               WHERE thread_id IS NOT NULL 
               AND thread_id IN (
                   SELECT DISTINCT thread_id 
                   FROM tweet 
                   WHERE status = 'failed' AND thread_id IS NOT NULL
               )'''
        ).fetchone()['count']
        
        automation_report['system_status'] = {
            'pending_threads_available': total_pending,
            'failed_threads_available': total_failed_threads
        }
        
        conn.close()
        
        # Operation 1: Post Pending Threads
        if config['post_pending'] and total_pending > 0:
            if config['dry_run']:
                automation_report['results']['pending_operation'] = {
                    'status': 'dry_run',
                    'message': f'DRY RUN: Would post {min(total_pending, config["max_threads_per_run"])} pending threads'
                }
            else:
                # Call our existing post-all-pending endpoint internally
                pending_result = post_all_pending_threads_internal(
                    max_threads=config['max_threads_per_run'],
                    delay_between_threads=config['delay_between_threads']
                )
                automation_report['results']['pending_operation'] = pending_result
                
                if pending_result.get('posted', 0) > 0:
                    automation_report['summary']['operations_completed'] += 1
                    automation_report['summary']['total_threads_processed'] += pending_result.get('threads_processed', 0)
                    automation_report['summary']['total_tweets_posted'] += pending_result.get('posted', 0)
                    automation_report['summary']['total_failures'] += pending_result.get('failed', 0)
        
        # Operation 2: Retry Failed Threads  
        if config['retry_failed'] and total_failed_threads > 0:
            if config['dry_run']:
                automation_report['results']['failed_retry_operation'] = {
                    'status': 'dry_run', 
                    'message': f'DRY RUN: Would retry {min(total_failed_threads, config["max_threads_per_run"])} failed threads'
                }
            else:
                # Call our existing retry-all-failed endpoint internally
                retry_result = retry_all_failed_threads_internal(
                    max_threads=config['max_threads_per_run'],
                    delay_between_threads=config['delay_between_threads']
                )
                automation_report['results']['failed_retry_operation'] = retry_result
                
                if retry_result.get('retried', 0) > 0:
                    automation_report['summary']['operations_completed'] += 1
                    automation_report['summary']['total_threads_processed'] += retry_result.get('threads_processed', 0)
                    automation_report['summary']['total_tweets_posted'] += retry_result.get('retried', 0)
                    automation_report['summary']['total_failures'] += retry_result.get('still_failed', 0)
        
        # Calculate execution time
        automation_end = datetime.now(UTC)
        automation_report['completed_at'] = automation_end.isoformat()
        automation_report['execution_time_seconds'] = (automation_end - automation_start).total_seconds()
        
        # Determine overall status
        if automation_report['summary']['operations_completed'] > 0:
            automation_report['status'] = 'success'
            automation_report['message'] = f'Automation completed: {automation_report["summary"]["total_tweets_posted"]} tweets posted across {automation_report["summary"]["total_threads_processed"]} threads'
        elif config['dry_run']:
            automation_report['status'] = 'dry_run_complete'
            automation_report['message'] = 'Dry run completed successfully'
        else:
            automation_report['status'] = 'no_work'
            automation_report['message'] = 'No pending or failed threads found to process'
        
        return jsonify(automation_report)
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'automation_id': f"auto_error_{int(datetime.now().timestamp())}",
            'timestamp': datetime.now(UTC).isoformat()
        }), 500

def post_all_pending_threads_internal(max_threads=10, delay_between_threads=5):
    """Internal function to post pending threads (used by automation)"""
    try:
        conn = get_db()
        
        # Get pending threads
        pending_threads_query = '''
            SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                   COUNT(*) as tweet_count
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.thread_id IS NOT NULL 
            AND t.status = 'pending'
            AND a.status != 'deleted'
            GROUP BY t.thread_id, t.twitter_account_id
            ORDER BY created_at ASC
            LIMIT ?
        '''
        pending_threads = conn.execute(pending_threads_query, (max_threads,)).fetchall()
        
        if not pending_threads:
            conn.close()
            return {'message': 'No pending threads found', 'posted': 0, 'failed': 0, 'threads_processed': 0}
        
        results = []
        total_posted = 0
        total_failed = 0
        
        for thread in pending_threads:
            thread_id = thread['thread_id']
            thread_account_id = thread['twitter_account_id']
            
            # Check rate limit
            from app.utils.rate_limit import get_rate_limit_status
            rate_status = get_rate_limit_status(thread_account_id)
            
            if rate_status['tweets_posted'] + thread['tweet_count'] > rate_status['limit']:
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'skipped_rate_limit',
                    'reason': f"Would exceed rate limit ({rate_status['tweets_posted']}/{rate_status['limit']})"
                })
                continue
            
            # Get tweets for this thread
            tweets = conn.execute(
                '''SELECT id, twitter_account_id, content, thread_position 
                   FROM tweet 
                   WHERE thread_id = ? AND status = 'pending'
                   ORDER BY thread_position''',
                (thread_id,)
            ).fetchall()
            
            if not tweets:
                continue
            
            # Post the thread
            posted_tweets = []
            failed_tweets = []
            previous_tweet_id = None
            
            for tweet in tweets:
                success, result = post_to_twitter(
                    tweet['twitter_account_id'], 
                    tweet['content'],
                    reply_to_tweet_id=previous_tweet_id
                )
                
                if success:
                    conn.execute(
                        '''UPDATE tweet 
                           SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                           WHERE id = ?''',
                        ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                    )
                    conn.commit()
                    posted_tweets.append({'tweet_id': tweet['id'], 'twitter_id': result, 'position': tweet['thread_position']})
                    previous_tweet_id = result
                else:
                    conn.execute('UPDATE tweet SET status = ? WHERE id = ?', ('failed', tweet['id']))
                    conn.commit()
                    failed_tweets.append({'tweet_id': tweet['id'], 'position': tweet['thread_position'], 'error': result})
                    break
            
            results.append({
                'thread_id': thread_id,
                'account_id': thread_account_id,
                'status': 'completed' if not failed_tweets else 'partial_failure',
                'posted_count': len(posted_tweets),
                'failed_count': len(failed_tweets)
            })
            
            total_posted += len(posted_tweets)
            total_failed += len(failed_tweets)
            
            # Add delay between threads
            if delay_between_threads > 0 and thread != pending_threads[-1]:
                import time
                time.sleep(delay_between_threads)
        
        conn.close()
        
        return {
            'message': f'Processed {len(pending_threads)} threads',
            'posted': total_posted,
            'failed': total_failed,
            'threads_processed': len(results),
            'results': results
        }
    
    except Exception as e:
        return {
            'error': str(e),
            'message': 'Internal function failed',
            'posted': 0,
            'failed': 0,
            'threads_processed': 0,
            'results': []
        }

def retry_all_failed_threads_internal(max_threads=10, delay_between_threads=5):
    """Internal function to retry failed threads (used by automation)"""
    try:
        conn = get_db()
        
        # Get failed threads
        failed_threads_query = '''
            SELECT DISTINCT t.thread_id, t.twitter_account_id, MIN(t.created_at) as created_at,
                   COUNT(*) as total_tweets,
                   SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_tweets,
                   SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_tweets
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.thread_id IS NOT NULL 
            AND a.status != 'deleted'
            AND t.thread_id IN (
                SELECT DISTINCT thread_id 
                FROM tweet 
                WHERE status = 'failed' AND thread_id IS NOT NULL
            )
            GROUP BY t.thread_id, t.twitter_account_id
            ORDER BY created_at ASC
            LIMIT ?
        '''
        failed_threads = conn.execute(failed_threads_query, (max_threads,)).fetchall()
        
        if not failed_threads:
            conn.close()
            return {'message': 'No failed threads found', 'retried': 0, 'still_failed': 0, 'threads_processed': 0}
        
        results = []
        total_retried = 0
        total_still_failed = 0
        
        for thread in failed_threads:
            thread_id = thread['thread_id']
            thread_account_id = thread['twitter_account_id']
            
            # Check rate limit
            from app.utils.rate_limit import get_rate_limit_status
            rate_status = get_rate_limit_status(thread_account_id)
            tweets_to_post = thread['failed_tweets'] + thread['pending_tweets']
            
            if rate_status['tweets_posted'] + tweets_to_post > rate_status['limit']:
                results.append({
                    'thread_id': thread_id,
                    'account_id': thread_account_id,
                    'status': 'skipped_rate_limit',
                    'reason': f"Would exceed rate limit ({rate_status['tweets_posted']}/{rate_status['limit']})"
                })
                continue
            
            # Reset failed tweets to pending
            reset_result = conn.execute(
                '''UPDATE tweet 
                   SET status = 'pending', twitter_id = NULL, posted_at = NULL, reply_to_tweet_id = NULL
                   WHERE thread_id = ? AND status = 'failed' ''',
                (thread_id,)
            )
            reset_count = reset_result.rowcount
            conn.commit()
            
            if reset_count == 0:
                continue
            
            # Get all pending tweets for this thread
            tweets = conn.execute(
                '''SELECT id, twitter_account_id, content, thread_position 
                   FROM tweet 
                   WHERE thread_id = ? AND status = 'pending'
                   ORDER BY thread_position''',
                (thread_id,)
            ).fetchall()
            
            # Find the last successfully posted tweet
            last_posted = conn.execute(
                '''SELECT twitter_id FROM tweet 
                   WHERE thread_id = ? AND status = 'posted'
                   ORDER BY thread_position DESC LIMIT 1''',
                (thread_id,)
            ).fetchone()
            
            previous_tweet_id = last_posted['twitter_id'] if last_posted else None
            
            # Post the remaining tweets
            posted_tweets = []
            failed_tweets = []
            
            for tweet in tweets:
                success, result = post_to_twitter(
                    tweet['twitter_account_id'], 
                    tweet['content'],
                    reply_to_tweet_id=previous_tweet_id
                )
                
                if success:
                    conn.execute(
                        '''UPDATE tweet 
                           SET status = ?, twitter_id = ?, posted_at = ?, reply_to_tweet_id = ?
                           WHERE id = ?''',
                        ('posted', result, datetime.now(UTC).isoformat(), previous_tweet_id, tweet['id'])
                    )
                    conn.commit()
                    posted_tweets.append({'tweet_id': tweet['id'], 'twitter_id': result, 'position': tweet['thread_position']})
                    previous_tweet_id = result
                else:
                    conn.execute('UPDATE tweet SET status = ? WHERE id = ?', ('failed', tweet['id']))
                    conn.commit()
                    failed_tweets.append({'tweet_id': tweet['id'], 'position': tweet['thread_position'], 'error': result})
                    break
            
            results.append({
                'thread_id': thread_id,
                'account_id': thread_account_id,
                'status': 'completed' if not failed_tweets else 'partial_failure',
                'reset_count': reset_count,
                'posted_count': len(posted_tweets),
                'failed_count': len(failed_tweets)
            })
            
            total_retried += len(posted_tweets)
            total_still_failed += len(failed_tweets)
            
            # Add delay between threads
            if delay_between_threads > 0 and thread != failed_threads[-1]:
                import time
                time.sleep(delay_between_threads)
        
        conn.close()
        
        return {
            'message': f'Processed {len(failed_threads)} failed threads',
            'retried': total_retried,
            'still_failed': total_still_failed,
            'threads_processed': len(results),
            'results': results
        }
    
    except Exception as e:
        return {'error': str(e), 'retried': 0, 'still_failed': 0, 'threads_processed': 0}