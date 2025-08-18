#!/usr/bin/env python3
"""
Fix DOK parsing for tweets at thread position 0

The original migration script only processed tweets at position 1 or NULL,
but some threads start at position 0. This script fixes that gap.
"""
import sqlite3
import re

def parse_dok_metadata(tweet_content):
    """Parse DOK metadata from tweet content (same as main app)"""
    pattern = r'^(?:[🟢❌]\s*)?(ADDED|DELETED):\s+(DOK[34]):'
    match = re.match(pattern, tweet_content.strip())
    if match:
        change_type = match.group(1)  # ADDED or DELETED
        dok_type = match.group(2)     # DOK3 or DOK4
        return dok_type, change_type
    return None, None

def main():
    conn = sqlite3.connect('instance/twitter_manager.db')
    
    print("Finding tweets at position 0 that need DOK processing...")
    
    # Find tweets at position 0 that are posted and don't have DOK data
    cursor = conn.execute('''
        SELECT id, content, thread_id, thread_position, twitter_account_id
        FROM tweet 
        WHERE thread_position = 0 
        AND status = 'posted'
        AND (dok_type IS NULL OR change_type IS NULL)
        ORDER BY id
    ''')
    
    tweets_to_process = cursor.fetchall()
    print(f'Found {len(tweets_to_process)} position-0 tweets to process')
    
    if len(tweets_to_process) == 0:
        print("No tweets need processing.")
        conn.close()
        return
    
    updates_count = 0
    for tweet in tweets_to_process:
        tweet_id, content, thread_id, thread_position, account_id = tweet
        dok_type, change_type = parse_dok_metadata(content)
        
        if dok_type and change_type:
            print(f'Processing tweet {tweet_id} (account {account_id}): {change_type} {dok_type}')
            print(f'  Content: {content[:80]}...')
            
            # Update the first tweet
            conn.execute('''
                UPDATE tweet 
                SET dok_type = ?, change_type = ? 
                WHERE id = ?
            ''', (dok_type, change_type, tweet_id))
            
            # Propagate to all tweets in the thread
            if thread_id:
                conn.execute('''
                    UPDATE tweet 
                    SET dok_type = ?, change_type = ? 
                    WHERE thread_id = ? AND id != ?
                ''', (dok_type, change_type, thread_id, tweet_id))
            
            updates_count += 1
    
    conn.commit()
    print(f'\nSuccessfully updated {updates_count} tweet records with DOK metadata')
    print("DOK parsing fix completed!")
    conn.close()

if __name__ == "__main__":
    main()