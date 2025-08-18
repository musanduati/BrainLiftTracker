"""DOK Tracking Utilities

Functions for parsing and managing DOK (Document) change tracking from tweet content.
"""

import re


def parse_dok_metadata(tweet_content):
    """Parse DOK metadata from tweet content
    
    Looks for patterns like:
    - ADDED: DOK3: ...
    - DELETED: DOK4: ...
    - UPDATED: DOK3: ...
    - 🟢 ADDED: DOK3: ...
    - ❌ DELETED: DOK4: ...
    - 🔄 UPDATED: DOK3: ...
    
    Args:
        tweet_content (str): The tweet text content
        
    Returns:
        tuple: (dok_type, change_type) or (None, None) if no pattern found
        
    Examples:
        >>> parse_dok_metadata("ADDED: DOK3: New feature implemented")
        ('DOK3', 'ADDED')
        
        >>> parse_dok_metadata("🟢 ADDED: DOK4: New feature with emoji")
        ('DOK4', 'ADDED')
        
        >>> parse_dok_metadata("❌ DELETED: DOK3: Removed functionality")
        ('DOK3', 'DELETED')
        
        >>> parse_dok_metadata("🔄 UPDATED: DOK4: Modified existing content")
        ('DOK4', 'UPDATED')
        
        >>> parse_dok_metadata("Regular tweet without DOK info")
        (None, None)
    """
    if not tweet_content:
        return None, None
    
    # Pattern to match optional emoji + ADDED/DELETED/UPDATED: DOK3/DOK4 at start of tweet
    # Handles: "ADDED: DOK3:", "🟢 ADDED: DOK4:", "❌ DELETED: DOK3:", "🔄 UPDATED: DOK4 (similarity):", etc.
    pattern = r'^(?:[🟢❌🔄]\s*)?(ADDED|DELETED|UPDATED):\s+(DOK[34])(?:\s*\([^)]*\))?:'
    
    match = re.match(pattern, tweet_content.strip())
    if match:
        change_type = match.group(1)  # ADDED, DELETED, or UPDATED
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
        'dok3_changes': {'added': 0, 'deleted': 0, 'updated': 0, 'total': 0},
        'dok4_changes': {'added': 0, 'deleted': 0, 'updated': 0, 'total': 0},
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
        
        if dok_type == 'DOK3' and change_type in ['added', 'deleted', 'updated']:
            stats['dok3_changes'][change_type] += count
            stats['dok3_changes']['total'] += count
        elif dok_type == 'DOK4' and change_type in ['added', 'deleted', 'updated']:
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
            COUNT(CASE WHEN t.dok_type = 'DOK3' AND t.change_type = 'UPDATED' THEN 1 END) as dok3_updated,
            COUNT(CASE WHEN t.dok_type = 'DOK4' AND t.change_type = 'ADDED' THEN 1 END) as dok4_added,
            COUNT(CASE WHEN t.dok_type = 'DOK4' AND t.change_type = 'DELETED' THEN 1 END) as dok4_deleted,
            COUNT(CASE WHEN t.dok_type = 'DOK4' AND t.change_type = 'UPDATED' THEN 1 END) as dok4_updated
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
                'updated': row['dok3_updated'],
                'total': row['dok3_added'] + row['dok3_deleted'] + row['dok3_updated']
            },
            'dok4_changes': {
                'added': row['dok4_added'],
                'deleted': row['dok4_deleted'],
                'updated': row['dok4_updated'],
                'total': row['dok4_added'] + row['dok4_deleted'] + row['dok4_updated']
            },
            'total_dok_changes': row['dok_tweets']
        }
        accounts.append(account)
    
    # Calculate aggregated summary for all accounts
    total_changes = sum(acc['total_dok_changes'] for acc in accounts)
    
    # Aggregate DOK3 changes
    dok3_total_added = sum(acc['dok3_changes']['added'] for acc in accounts)
    dok3_total_updated = sum(acc['dok3_changes']['updated'] for acc in accounts)
    dok3_total_deleted = sum(acc['dok3_changes']['deleted'] for acc in accounts)
    dok3_total = dok3_total_added + dok3_total_updated + dok3_total_deleted
    
    # Aggregate DOK4 changes  
    dok4_total_added = sum(acc['dok4_changes']['added'] for acc in accounts)
    dok4_total_updated = sum(acc['dok4_changes']['updated'] for acc in accounts)
    dok4_total_deleted = sum(acc['dok4_changes']['deleted'] for acc in accounts)
    dok4_total = dok4_total_added + dok4_total_updated + dok4_total_deleted
    
    return {
        'accounts': accounts,
        'summary': {
            'total_accounts': len(accounts),
            'total_changes': total_changes,
            'dok3_changes': {
                'added': dok3_total_added,
                'updated': dok3_total_updated,
                'deleted': dok3_total_deleted,
                'total': dok3_total
            },
            'dok4_changes': {
                'added': dok4_total_added,
                'updated': dok4_total_updated,  
                'deleted': dok4_total_deleted,
                'total': dok4_total
            }
        }
    }