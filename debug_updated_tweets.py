#!/usr/bin/env python3
"""
Debug script to find tweets with UPDATED patterns that aren't being parsed
"""

import sqlite3
import os
import sys
import re

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.dok_parser import parse_dok_metadata

def get_db_path():
    """Get the database path (same logic as main app)"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'twitter_manager.db')

def debug_unprocessed_tweets():
    """Debug tweets that should have DOK metadata but don't"""
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get tweets that are thread starters (position 0 or 1) or standalone tweets
    # that don't have DOK metadata yet
    cursor = conn.execute('''
        SELECT id, content, thread_id, thread_position
        FROM tweet 
        WHERE (thread_position IN (0, 1) OR thread_position IS NULL OR thread_id IS NULL)
        AND (dok_type IS NULL OR change_type IS NULL)
        ORDER BY id
        LIMIT 20
    ''')
    
    tweets_to_check = cursor.fetchall()
    print(f"Found {len(tweets_to_check)} tweets without DOK metadata")
    print("=" * 80)
    
    updated_count = 0
    
    for i, tweet in enumerate(tweets_to_check, 1):
        content = tweet['content']
        dok_type, change_type = parse_dok_metadata(content)
        
        print(f"{i}. Tweet ID: {tweet['id']}")
        print(f"   Thread: {tweet['thread_id']} (pos: {tweet['thread_position']})")
        print(f"   Content: {content[:100]}...")
        print(f"   Parsed: {dok_type}, {change_type}")
        
        # Check if it contains UPDATED pattern manually
        if 'UPDATED' in content.upper():
            print(f"   >>> Contains UPDATED keyword!")
            updated_count += 1
            
        # Check for specific emojis
        if '🔄' in content:
            print(f"   >>> Contains 🔄 emoji!")
            
        print()
    
    print("=" * 80)
    print(f"Summary: {updated_count} tweets contain 'UPDATED' keyword")
    
    # Also check for any tweets that already have UPDATED in database
    cursor = conn.execute('''
        SELECT COUNT(*) as count
        FROM tweet 
        WHERE change_type = 'UPDATED'
    ''')
    existing_updated = cursor.fetchone()['count']
    print(f"Existing UPDATED tweets in database: {existing_updated}")
    
    conn.close()

if __name__ == "__main__":
    debug_unprocessed_tweets()