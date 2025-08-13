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
        
        # Create all tweets in the thread as pending
        created_tweets = []
        for i, tweet_text in enumerate(tweets):
            cursor = conn.execute(
                '''INSERT INTO tweet (twitter_account_id, content, thread_id, thread_position, status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (account_id, tweet_text, thread_id, i, 'pending')
            )
            tweet_id = cursor.lastrowid
            created_tweets.append({
                'id': tweet_id,
                'position': i,
                'content': tweet_text
            })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Thread created with {len(tweets)} tweets',
            'thread_id': thread_id,
            'tweets': created_tweets
        }), 201
    
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
                thread_id,
                twitter_account_id,
                COUNT(*) as tweet_count,
                MIN(created_at) as created_at,
                SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted_count,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM tweet
            WHERE thread_id IS NOT NULL
            GROUP BY thread_id, twitter_account_id
            ORDER BY created_at DESC
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
                'username': account['username'] if account else 'Unknown',
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