#!/usr/bin/env python3
"""
Debug script to test the posts API endpoint locally
"""

import sqlite3
import os
import sys

def get_db_path():
    """Get the database path"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'twitter_manager.db')

def test_posts_queries():
    """Test the queries used in the posts API endpoint"""
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("Testing Posts API Queries")
    print("=" * 50)
    
    try:
        # Test the tweets query that was causing issues
        print("1. Testing tweets query...")
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
            LIMIT 5
        ''').fetchall()
        
        print(f"   SUCCESS: Retrieved {len(tweets)} tweets")
        if tweets:
            print(f"   Sample tweet: ID={tweets[0]['id']}, username={tweets[0]['username']}")
        
    except Exception as e:
        print(f"   ERROR in tweets query: {e}")
        return
    
    try:
        # Test the threads query (updated to use tweet table)
        print("\n2. Testing threads query...")
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
            LIMIT 5
        ''').fetchall()
        
        print(f"   SUCCESS: Retrieved {len(threads)} threads")
        if threads:
            print(f"   Sample thread: ID={threads[0]['thread_id']}, username={threads[0]['username']}")
            
    except Exception as e:
        print(f"   ERROR in threads query: {e}")
        return
    
    try:
        # Test basic table structure
        print("\n3. Testing table structures...")
        
        # Check tweet table columns
        tweet_columns = conn.execute("PRAGMA table_info(tweet)").fetchall()
        tweet_col_names = [col[1] for col in tweet_columns]
        print(f"   Tweet table columns: {tweet_col_names}")
        
        # Check twitter_account table columns
        account_columns = conn.execute("PRAGMA table_info(twitter_account)").fetchall()
        account_col_names = [col[1] for col in account_columns]
        print(f"   Account table columns: {account_col_names}")
        
        # Check if thread table exists
        thread_exists = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='thread'
        """).fetchone()
        
        if thread_exists:
            thread_columns = conn.execute("PRAGMA table_info(thread)").fetchall()
            thread_col_names = [col[1] for col in thread_columns]
            print(f"   Thread table columns: {thread_col_names}")
        else:
            print("   WARNING: Thread table does not exist!")
            
    except Exception as e:
        print(f"   ERROR checking table structures: {e}")
    
    conn.close()
    print("\n" + "=" * 50)
    print("Debug complete. If no errors above, the issue might be in Flask routing or authentication.")

if __name__ == "__main__":
    test_posts_queries()