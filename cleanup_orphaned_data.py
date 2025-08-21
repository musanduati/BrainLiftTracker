#!/usr/bin/env python3
"""
Cleanup Script: Remove Orphaned Data

This script identifies and removes orphaned data in the database:
1. Tweets without valid accounts
2. Lists without valid owners
3. List memberships for deleted accounts
4. Followers for deleted accounts

Run this script to clean up existing orphaned data before or after migration.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add the app directory to the path so we can import config
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
from app.core.config import Config

def analyze_orphaned_data():
    """Analyze orphaned data in the database"""
    print("🔍 Analyzing orphaned data...")
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Find orphaned tweets
        orphaned_tweets = conn.execute('''
            SELECT t.id, t.twitter_account_id, t.content, t.status, t.thread_id, t.created_at
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL
            ORDER BY t.created_at DESC
            LIMIT 10
        ''').fetchall()
        
        orphaned_tweet_count = conn.execute('''
            SELECT COUNT(*) as count
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()['count']
        
        # Find orphaned lists
        orphaned_lists = conn.execute('''
            SELECT l.id, l.name, l.owner_account_id, l.created_at
            FROM twitter_list l
            LEFT JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE a.id IS NULL
            ORDER BY l.created_at DESC
            LIMIT 10
        ''').fetchall()
        
        orphaned_list_count = conn.execute('''
            SELECT COUNT(*) as count
            FROM twitter_list l
            LEFT JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()['count']
        
        # Find orphaned list memberships (these should auto-cleanup with CASCADE but check anyway)
        orphaned_memberships = conn.execute('''
            SELECT lm.id, lm.account_id, lm.list_id
            FROM list_membership lm
            LEFT JOIN twitter_account a ON lm.account_id = a.id
            WHERE a.id IS NULL
            LIMIT 10
        ''').fetchall()
        
        orphaned_membership_count = conn.execute('''
            SELECT COUNT(*) as count
            FROM list_membership lm
            LEFT JOIN twitter_account a ON lm.account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()['count']
        
        # Find orphaned followers (these should auto-cleanup with CASCADE but check anyway)
        orphaned_followers = conn.execute('''
            SELECT f.id, f.account_id, f.follower_username
            FROM follower f
            LEFT JOIN twitter_account a ON f.account_id = a.id
            WHERE a.id IS NULL
            LIMIT 10
        ''').fetchall()
        
        orphaned_follower_count = conn.execute('''
            SELECT COUNT(*) as count
            FROM follower f
            LEFT JOIN twitter_account a ON f.account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()['count']
        
        # Find threads that would become orphaned
        orphaned_threads = conn.execute('''
            SELECT t.thread_id, COUNT(*) as tweet_count, t.twitter_account_id
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL AND t.thread_id IS NOT NULL
            GROUP BY t.thread_id, t.twitter_account_id
            ORDER BY tweet_count DESC
            LIMIT 10
        ''').fetchall()
        
        total_orphaned_thread_tweets = conn.execute('''
            SELECT COUNT(*) as count
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL AND t.thread_id IS NOT NULL
        ''').fetchone()['count']
        
        conn.close()
        
        print(f"📊 Found {orphaned_tweet_count} orphaned tweets")
        if orphaned_tweets:
            print("   Sample orphaned tweets:")
            for tweet in orphaned_tweets[:5]:
                content = tweet['content'][:50] + "..." if len(tweet['content']) > 50 else tweet['content']
                print(f"     ID {tweet['id']}: Account {tweet['twitter_account_id']} - \"{content}\"")
        
        print(f"📊 Found {orphaned_list_count} orphaned lists")
        if orphaned_lists:
            print("   Sample orphaned lists:")
            for list_item in orphaned_lists[:5]:
                print(f"     ID {list_item['id']}: \"{list_item['name']}\" (Owner: {list_item['owner_account_id']})")
        
        print(f"📊 Found {orphaned_membership_count} orphaned list memberships")
        print(f"📊 Found {orphaned_follower_count} orphaned followers")
        print(f"📊 Found {len(orphaned_threads)} orphaned threads with {total_orphaned_thread_tweets} tweets")
        
        if orphaned_threads:
            print("   Sample orphaned threads:")
            for thread in orphaned_threads[:5]:
                print(f"     Thread {thread['thread_id']}: {thread['tweet_count']} tweets (Account: {thread['twitter_account_id']})")
        
        return {
            'tweets': orphaned_tweet_count,
            'lists': orphaned_list_count,
            'memberships': orphaned_membership_count,
            'followers': orphaned_follower_count,
            'thread_tweets': total_orphaned_thread_tweets,
            'thread_count': len(orphaned_threads)
        }
        
    except Exception as e:
        print(f"❌ Error analyzing data: {e}")
        return None

def cleanup_orphaned_data(dry_run=True):
    """Clean up orphaned data"""
    action = "Would delete" if dry_run else "Deleting"
    print(f"\n🧹 {action} orphaned data..." + (" (DRY RUN)" if dry_run else ""))
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        conn.row_factory = sqlite3.Row
        
        if not dry_run:
            conn.execute('BEGIN TRANSACTION')
        
        # Clean up orphaned tweets
        if dry_run:
            tweet_count = conn.execute('''
                SELECT COUNT(*) as count
                FROM tweet t
                LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
                WHERE a.id IS NULL
            ''').fetchone()['count']
        else:
            result = conn.execute('''
                DELETE FROM tweet
                WHERE twitter_account_id NOT IN (SELECT id FROM twitter_account)
            ''')
            tweet_count = result.rowcount
        
        print(f"  {action} {tweet_count} orphaned tweets")
        
        # Clean up orphaned lists
        if dry_run:
            list_count = conn.execute('''
                SELECT COUNT(*) as count
                FROM twitter_list l
                LEFT JOIN twitter_account a ON l.owner_account_id = a.id
                WHERE a.id IS NULL
            ''').fetchone()['count']
        else:
            result = conn.execute('''
                DELETE FROM twitter_list
                WHERE owner_account_id NOT IN (SELECT id FROM twitter_account)
            ''')
            list_count = result.rowcount
        
        print(f"  {action} {list_count} orphaned lists")
        
        # Clean up orphaned list memberships (should be automatic with CASCADE)
        if dry_run:
            membership_count = conn.execute('''
                SELECT COUNT(*) as count
                FROM list_membership lm
                LEFT JOIN twitter_account a ON lm.account_id = a.id
                WHERE a.id IS NULL
            ''').fetchone()['count']
        else:
            result = conn.execute('''
                DELETE FROM list_membership
                WHERE account_id NOT IN (SELECT id FROM twitter_account)
            ''')
            membership_count = result.rowcount
        
        print(f"  {action} {membership_count} orphaned list memberships")
        
        # Clean up orphaned followers (should be automatic with CASCADE)
        if dry_run:
            follower_count = conn.execute('''
                SELECT COUNT(*) as count
                FROM follower f
                LEFT JOIN twitter_account a ON f.account_id = a.id
                WHERE a.id IS NULL
            ''').fetchone()['count']
        else:
            result = conn.execute('''
                DELETE FROM follower
                WHERE account_id NOT IN (SELECT id FROM twitter_account)
            ''')
            follower_count = result.rowcount
        
        print(f"  {action} {follower_count} orphaned followers")
        
        if not dry_run:
            conn.commit()
            print("✅ Cleanup completed successfully")
        else:
            print("ℹ️  Run with --execute to perform actual cleanup")
        
        conn.close()
        
        return {
            'tweets': tweet_count,
            'lists': list_count,
            'memberships': membership_count,
            'followers': follower_count
        }
        
    except Exception as e:
        if not dry_run:
            conn.rollback()
        conn.close()
        print(f"❌ Error during cleanup: {e}")
        return None

def find_deleted_accounts():
    """Find accounts marked as deleted"""
    print("\n🔍 Finding deleted accounts...")
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Check if status column exists
        columns = conn.execute("PRAGMA table_info(twitter_account)").fetchall()
        has_status = any(col[1] == 'status' for col in columns)
        
        if not has_status:
            print("ℹ️  Status column doesn't exist yet - no soft-deleted accounts to process")
            return []
        
        deleted_accounts = conn.execute('''
            SELECT id, username, status, created_at,
                   (SELECT COUNT(*) FROM tweet WHERE twitter_account_id = twitter_account.id) as tweet_count,
                   (SELECT COUNT(DISTINCT thread_id) FROM tweet WHERE twitter_account_id = twitter_account.id AND thread_id IS NOT NULL) as thread_count
            FROM twitter_account
            WHERE status = 'deleted'
            ORDER BY created_at DESC
        ''').fetchall()
        
        conn.close()
        
        if deleted_accounts:
            print(f"📊 Found {len(deleted_accounts)} deleted accounts:")
            for account in deleted_accounts:
                print(f"   @{account['username']} (ID: {account['id']}) - {account['tweet_count']} tweets, {account['thread_count']} threads")
        else:
            print("📊 No deleted accounts found")
        
        return deleted_accounts
        
    except Exception as e:
        print(f"❌ Error finding deleted accounts: {e}")
        return []

def main():
    """Main cleanup function"""
    print("🚀 Twitter Manager - Orphaned Data Cleanup")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(Config.DB_PATH):
        print(f"❌ Database not found at {Config.DB_PATH}")
        return False
    
    # Parse command line arguments
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] in ['--execute', '-x']:
        dry_run = False
    
    # Analyze current state
    orphaned_data = analyze_orphaned_data()
    if not orphaned_data:
        return False
    
    # Find deleted accounts
    deleted_accounts = find_deleted_accounts()
    
    # Calculate total orphaned items
    total_orphaned = sum(orphaned_data.values())
    
    if total_orphaned == 0:
        print("\n✅ No orphaned data found - database is clean!")
        return True
    
    print(f"\n📋 Summary: {total_orphaned} orphaned items found")
    
    if dry_run:
        print("\n⚠️  This is a DRY RUN - no data will be deleted")
        print("Use --execute or -x flag to perform actual cleanup")
    else:
        print(f"\n⚠️  This will permanently delete {total_orphaned} orphaned items!")
        response = input("Continue with cleanup? (y/N): ").lower()
        if response != 'y':
            print("Cleanup aborted by user")
            return False
    
    # Perform cleanup
    cleanup_results = cleanup_orphaned_data(dry_run)
    
    if cleanup_results and not dry_run:
        print(f"\n✅ Cleanup completed successfully!")
        print(f"   Deleted {cleanup_results['tweets']} tweets")
        print(f"   Deleted {cleanup_results['lists']} lists")
        print(f"   Deleted {cleanup_results['memberships']} list memberships")
        print(f"   Deleted {cleanup_results['followers']} followers")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)