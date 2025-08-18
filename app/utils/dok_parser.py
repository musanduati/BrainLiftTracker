"""DOK Tracking Utilities

Functions for parsing and managing DOK (Document) change tracking from tweet content.
"""

import re


def parse_dok_metadata(tweet_content):
    """Parse DOK metadata from tweet content
    
    Looks for patterns like:
    - ADDED: DOK3: ...
    - DELETED: DOK4: ...
    
    Args:
        tweet_content (str): The tweet text content
        
    Returns:
        tuple: (dok_type, change_type) or (None, None) if no pattern found
        
    Examples:
        >>> parse_dok_metadata("ADDED: DOK3: New feature implemented")
        ('DOK3', 'ADDED')
        
        >>> parse_dok_metadata("DELETED: DOK4: Removed old functionality")
        ('DOK4', 'DELETED')
        
        >>> parse_dok_metadata("Regular tweet without DOK info")
        (None, None)
    """
    if not tweet_content:
        return None, None
    
    # Pattern to match ADDED/DELETED: DOK3/DOK4: at start of tweet
    pattern = r'^(ADDED|DELETED):\s+(DOK[34]):'
    
    match = re.match(pattern, tweet_content.strip())
    if match:
        change_type = match.group(1)  # ADDED or DELETED
        dok_type = match.group(2)     # DOK3 or DOK4
        return dok_type, change_type
    
    return None, None


def propagate_dok_metadata_to_thread(conn, thread_id, dok_type, change_type):
    """Propagate DOK metadata from first tweet to all tweets in thread
    
    Args:
        conn: Database connection
        thread_id (str): Thread ID to update
        dok_type (str): DOK type (DOK3/DOK4) 
        change_type (str): Change type (ADDED/DELETED)
    """
    if not thread_id or not dok_type or not change_type:
        return
    
    conn.execute('''
        UPDATE tweet 
        SET dok_type = ?, change_type = ? 
        WHERE thread_id = ?
    ''', (dok_type, change_type, thread_id))


def get_dok_stats_for_account(conn, account_id, start_date=None, end_date=None):
    """Get DOK statistics for a specific account
    
    Args:
        conn: Database connection
        account_id (int): Account ID to analyze
        start_date (str, optional): Start date filter (ISO format)
        end_date (str, optional): End date filter (ISO format)
        
    Returns:
        dict: DOK statistics breakdown
    """
    base_query = '''
        SELECT 
            dok_type,
            change_type,
            COUNT(*) as count
        FROM tweet 
        WHERE twitter_account_id = ?
        AND dok_type IS NOT NULL 
        AND change_type IS NOT NULL
    '''
    
    params = [account_id]
    
    if start_date:
        base_query += ' AND created_at >= ?'
        params.append(start_date)
    
    if end_date:
        base_query += ' AND created_at <= ?'
        params.append(end_date)
    
    base_query += ' GROUP BY dok_type, change_type ORDER BY dok_type, change_type'
    
    cursor = conn.execute(base_query, params)
    results = cursor.fetchall()
    
    # Format results
    stats = {
        'total_changes': 0,
        'dok3_changes': {'added': 0, 'deleted': 0, 'total': 0},
        'dok4_changes': {'added': 0, 'deleted': 0, 'total': 0},
        'breakdown': []
    }
    
    for row in results:
        dok_type = row['dok_type']
        change_type = row['change_type'].lower()
        count = row['count']
        
        stats['total_changes'] += count
        stats['breakdown'].append({
            'dok_type': dok_type,
            'change_type': change_type,
            'count': count
        })
        
        if dok_type == 'DOK3':
            stats['dok3_changes'][change_type] += count
            stats['dok3_changes']['total'] += count
        elif dok_type == 'DOK4':
            stats['dok4_changes'][change_type] += count
            stats['dok4_changes']['total'] += count
    
    return stats


def get_all_accounts_dok_summary(conn):
    """Get DOK summary for all accounts
    
    Args:
        conn: Database connection
        
    Returns:
        dict: Summary of DOK changes across all accounts
    """
    cursor = conn.execute('''
        SELECT 
            ta.id,
            ta.username,
            ta.display_name,
            COUNT(t.id) as total_tweets,
            COUNT(CASE WHEN t.dok_type IS NOT NULL THEN 1 END) as dok_tweets,
            COUNT(CASE WHEN t.dok_type = 'DOK3' AND t.change_type = 'ADDED' THEN 1 END) as dok3_added,
            COUNT(CASE WHEN t.dok_type = 'DOK3' AND t.change_type = 'DELETED' THEN 1 END) as dok3_deleted,
            COUNT(CASE WHEN t.dok_type = 'DOK4' AND t.change_type = 'ADDED' THEN 1 END) as dok4_added,
            COUNT(CASE WHEN t.dok_type = 'DOK4' AND t.change_type = 'DELETED' THEN 1 END) as dok4_deleted
        FROM twitter_account ta
        LEFT JOIN tweet t ON ta.id = t.twitter_account_id
        GROUP BY ta.id, ta.username, ta.display_name
        HAVING total_tweets > 0
        ORDER BY dok_tweets DESC, total_tweets DESC
    ''')
    
    accounts = []
    for row in cursor.fetchall():
        account = {
            'id': row['id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'total_tweets': row['total_tweets'],
            'dok_tweets': row['dok_tweets'],
            'dok3_changes': {
                'added': row['dok3_added'],
                'deleted': row['dok3_deleted'],
                'total': row['dok3_added'] + row['dok3_deleted']
            },
            'dok4_changes': {
                'added': row['dok4_added'],
                'deleted': row['dok4_deleted'],
                'total': row['dok4_added'] + row['dok4_deleted']
            },
            'total_dok_changes': row['dok_tweets']
        }
        accounts.append(account)
    
    return {
        'accounts': accounts,
        'summary': {
            'total_accounts': len(accounts),
            'total_dok_changes': sum(acc['total_dok_changes'] for acc in accounts),
            'total_dok3_changes': sum(acc['dok3_changes']['total'] for acc in accounts),
            'total_dok4_changes': sum(acc['dok4_changes']['total'] for acc in accounts)
        }
    }