from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key
from app.utils.dok_parser import get_dok_stats_for_account, get_all_accounts_dok_summary

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/api/v1/analytics/dok-summary', methods=['GET'])
@require_api_key
def get_dok_summary():
    """Get overall DOK statistics across all accounts"""
    try:
        conn = get_db()
        summary = get_all_accounts_dok_summary(conn)
        conn.close()
        
        return jsonify(summary)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/v1/analytics/dok-summary/<int:account_id>', methods=['GET'])
@require_api_key
def get_account_dok_summary(account_id):
    """Get DOK statistics for a specific account"""
    try:
        conn = get_db()
        
        # Verify account exists
        account = conn.execute(
            'SELECT username, display_name FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Get date filters from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        stats = get_dok_stats_for_account(conn, account_id, start_date, end_date)
        conn.close()
        
        return jsonify({
            'account_id': account_id,
            'username': account['username'],
            'display_name': account['display_name'],
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/v1/analytics/progress-bar/<int:account_id>', methods=['GET'])
@require_api_key
def get_progress_bar_data(account_id):
    """Get progress bar data optimized for frontend display"""
    try:
        conn = get_db()
        
        # Verify account exists
        account = conn.execute(
            'SELECT username, display_name FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Get DOK statistics
        stats = get_dok_stats_for_account(conn, account_id)
        
        # Get total tweet count for this account
        total_tweets = conn.execute(
            'SELECT COUNT(*) as count FROM tweet WHERE twitter_account_id = ?',
            (account_id,)
        ).fetchone()['count']
        
        conn.close()
        
        # Format for progress bar
        progress_data = {
            'account': {
                'id': account_id,
                'username': account['username'],
                'display_name': account['display_name']
            },
            'overview': {
                'total_tweets': total_tweets,
                'total_changes': stats['total_changes'],
                'change_percentage': (stats['total_changes'] / total_tweets * 100) if total_tweets > 0 else 0
            },
            'dok_breakdown': {
                'dok3': {
                    'added': stats['dok3_changes']['added'],
                    'deleted': stats['dok3_changes']['deleted'],
                    'updated': stats['dok3_changes']['updated'],
                    'total': stats['dok3_changes']['total'],
                    'percentage': (stats['dok3_changes']['total'] / stats['total_changes'] * 100) if stats['total_changes'] > 0 else 0
                },
                'dok4': {
                    'added': stats['dok4_changes']['added'],
                    'deleted': stats['dok4_changes']['deleted'],
                    'updated': stats['dok4_changes']['updated'],
                    'total': stats['dok4_changes']['total'],
                    'percentage': (stats['dok4_changes']['total'] / stats['total_changes'] * 100) if stats['total_changes'] > 0 else 0
                }
            },
            'change_breakdown': {
                'added': stats['dok3_changes']['added'] + stats['dok4_changes']['added'],
                'deleted': stats['dok3_changes']['deleted'] + stats['dok4_changes']['deleted'],
                'updated': stats['dok3_changes']['updated'] + stats['dok4_changes']['updated']
            }
        }
        
        return jsonify(progress_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/v1/analytics/dok-timeline/<int:account_id>', methods=['GET'])
@require_api_key
def get_dok_timeline(account_id):
    """Get DOK changes over time for timeline visualization"""
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
        
        # Get DOK changes grouped by date
        timeline_data = conn.execute('''
            SELECT 
                DATE(created_at) as date,
                dok_type,
                change_type,
                COUNT(*) as count
            FROM tweet 
            WHERE twitter_account_id = ?
            AND dok_type IS NOT NULL 
            AND change_type IS NOT NULL
            GROUP BY DATE(created_at), dok_type, change_type
            ORDER BY date DESC
        ''', (account_id,)).fetchall()
        
        conn.close()
        
        # Format timeline data
        timeline = []
        for row in timeline_data:
            timeline.append({
                'date': row['date'],
                'dok_type': row['dok_type'],
                'change_type': row['change_type'],
                'count': row['count']
            })
        
        return jsonify({
            'account_id': account_id,
            'username': account['username'],
            'timeline': timeline
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/v1/analytics/dok-leaderboard', methods=['GET'])
@require_api_key
def get_dok_leaderboard():
    """Get leaderboard of accounts by DOK change activity"""
    try:
        conn = get_db()
        
        leaderboard = conn.execute('''
            SELECT 
                ta.id,
                ta.username,
                ta.display_name,
                COUNT(t.id) as total_dok_changes,
                COUNT(CASE WHEN t.dok_type = 'DOK3' THEN 1 END) as dok3_changes,
                COUNT(CASE WHEN t.dok_type = 'DOK4' THEN 1 END) as dok4_changes,
                COUNT(CASE WHEN t.change_type = 'ADDED' THEN 1 END) as added_changes,
                COUNT(CASE WHEN t.change_type = 'DELETED' THEN 1 END) as deleted_changes,
                COUNT(CASE WHEN t.change_type = 'UPDATED' THEN 1 END) as updated_changes,
                MAX(t.created_at) as last_change_date
            FROM twitter_account ta
            LEFT JOIN tweet t ON ta.id = t.twitter_account_id 
                AND t.dok_type IS NOT NULL 
                AND t.change_type IS NOT NULL
            GROUP BY ta.id, ta.username, ta.display_name
            HAVING total_dok_changes > 0
            ORDER BY total_dok_changes DESC, last_change_date DESC
        ''').fetchall()
        
        conn.close()
        
        # Format leaderboard
        formatted_leaderboard = []
        for i, account in enumerate(leaderboard):
            formatted_leaderboard.append({
                'rank': i + 1,
                'account_id': account['id'],
                'username': account['username'],
                'display_name': account['display_name'],
                'total_changes': account['total_dok_changes'],
                'dok3_changes': account['dok3_changes'],
                'dok4_changes': account['dok4_changes'],
                'added_changes': account['added_changes'],
                'deleted_changes': account['deleted_changes'],
                'updated_changes': account['updated_changes'],
                'last_change_date': account['last_change_date']
            })
        
        return jsonify({
            'leaderboard': formatted_leaderboard,
            'total_accounts': len(formatted_leaderboard)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/v1/analytics/dok-search', methods=['GET'])
@require_api_key
def search_dok_tweets():
    """Search for tweets with specific DOK patterns"""
    try:
        dok_type = request.args.get('dok_type')  # DOK3 or DOK4
        change_type = request.args.get('change_type')  # ADDED or DELETED
        account_id = request.args.get('account_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db()
        
        # Build query
        query = '''
            SELECT 
                t.id,
                t.content,
                t.dok_type,
                t.change_type,
                t.created_at,
                t.status,
                a.username,
                a.display_name
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.dok_type IS NOT NULL AND t.change_type IS NOT NULL
        '''
        params = []
        
        if dok_type:
            query += ' AND t.dok_type = ?'
            params.append(dok_type)
        
        if change_type:
            query += ' AND t.change_type = ?'
            params.append(change_type)
        
        if account_id:
            query += ' AND t.twitter_account_id = ?'
            params.append(account_id)
        
        query += ' ORDER BY t.created_at DESC LIMIT ?'
        params.append(limit)
        
        tweets = conn.execute(query, params).fetchall()
        conn.close()
        
        # Format results
        results = []
        for tweet in tweets:
            results.append({
                'id': tweet['id'],
                'content': tweet['content'][:200] + '...' if len(tweet['content']) > 200 else tweet['content'],
                'dok_type': tweet['dok_type'],
                'change_type': tweet['change_type'],
                'created_at': tweet['created_at'],
                'status': tweet['status'],
                'account': {
                    'username': tweet['username'],
                    'display_name': tweet['display_name']
                }
            })
        
        return jsonify({
            'tweets': results,
            'count': len(results),
            'filters': {
                'dok_type': dok_type,
                'change_type': change_type,
                'account_id': account_id,
                'limit': limit
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500