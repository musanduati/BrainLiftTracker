#!/usr/bin/env python3
"""
CASCADE Deployment with Orphaned Data Cleanup

This script handles the FOREIGN KEY constraint failed error by automatically
cleaning up orphaned data before applying CASCADE constraints.

Fixes: "FOREIGN KEY constraint failed" during CASCADE deployment
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime

def cleanup_orphaned_data(db_path):
    """Clean up orphaned data before CASCADE deployment"""
    print("Step 3.5: Cleaning up orphaned data...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('BEGIN TRANSACTION')
        
        # Clean up orphaned tweets
        result = conn.execute('''
            DELETE FROM tweet
            WHERE twitter_account_id NOT IN (SELECT id FROM twitter_account)
        ''')
        deleted_tweets = result.rowcount
        print(f"   - Cleaned up {deleted_tweets} orphaned tweets")
        
        # Clean up orphaned lists
        result = conn.execute('''
            DELETE FROM twitter_list
            WHERE owner_account_id NOT IN (SELECT id FROM twitter_account)
        ''')
        deleted_lists = result.rowcount
        print(f"   - Cleaned up {deleted_lists} orphaned lists")
        
        # Clean up orphaned list memberships
        try:
            result = conn.execute('''
                DELETE FROM list_membership
                WHERE account_id NOT IN (SELECT id FROM twitter_account)
                   OR list_id NOT IN (SELECT id FROM twitter_list)
            ''')
            deleted_memberships = result.rowcount
            print(f"   - Cleaned up {deleted_memberships} orphaned list memberships")
        except sqlite3.OperationalError:
            print("   - list_membership table not found, skipping")
        
        # Clean up orphaned followers
        try:
            result = conn.execute('''
                DELETE FROM follower
                WHERE account_id NOT IN (SELECT id FROM twitter_account)
            ''')
            deleted_followers = result.rowcount
            print(f"   - Cleaned up {deleted_followers} orphaned followers")
        except sqlite3.OperationalError:
            print("   - follower table not found, skipping")
        
        conn.commit()
        conn.close()
        
        total_cleaned = deleted_tweets + deleted_lists
        print(f"   SUCCESS: Cleaned up {total_cleaned} orphaned records")
        
        return {
            'tweets': deleted_tweets,
            'lists': deleted_lists,
            'total': total_cleaned
        }
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"   ERROR: Orphaned data cleanup failed: {e}")
        return None

def deploy_cascade_constraints_safe(db_path):
    """Deploy CASCADE constraints with orphaned data cleanup"""
    print("Step 4: Deploying CASCADE constraints (with cleanup)...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = OFF')  # Disable temporarily during migration
        conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        
        print("   - Creating backup tables...")
        conn.execute('CREATE TABLE tweet_backup AS SELECT * FROM tweet')
        conn.execute('CREATE TABLE twitter_list_backup AS SELECT * FROM twitter_list')
        
        print("   - Recreating tweet table with CASCADE...")
        conn.execute('DROP TABLE tweet')
        
        conn.execute('''
            CREATE TABLE tweet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_account_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                twitter_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                posted_at DATETIME, 
                thread_id TEXT, 
                reply_to_tweet_id TEXT, 
                thread_position INTEGER, 
                dok_type VARCHAR(10), 
                change_type VARCHAR(10),
                FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id) ON DELETE CASCADE
            )
        ''')
        
        # Only restore data that has valid foreign keys
        conn.execute('''
            INSERT INTO tweet 
            SELECT * FROM tweet_backup t 
            WHERE t.twitter_account_id IN (SELECT id FROM twitter_account)
        ''')
        
        print("   - Recreating twitter_list table with CASCADE...")
        conn.execute('DROP TABLE twitter_list')
        
        conn.execute('''
            CREATE TABLE twitter_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                mode TEXT DEFAULT 'private',
                owner_account_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME, 
                source VARCHAR(20) DEFAULT "created", 
                external_owner_username VARCHAR(255), 
                last_synced_at DATETIME, 
                is_managed BOOLEAN DEFAULT 1,
                FOREIGN KEY (owner_account_id) REFERENCES twitter_account(id) ON DELETE CASCADE
            )
        ''')
        
        # Only restore lists that have valid owners
        conn.execute('''
            INSERT INTO twitter_list 
            SELECT * FROM twitter_list_backup l 
            WHERE l.owner_account_id IN (SELECT id FROM twitter_account)
        ''')
        
        print("   - Cleaning up backup tables...")
        conn.execute('DROP TABLE tweet_backup')
        conn.execute('DROP TABLE twitter_list_backup')
        
        print("   - Re-enabling foreign keys...")
        conn.commit()
        conn.execute('PRAGMA foreign_keys = ON')
        conn.close()
        
        print("   SUCCESS: CASCADE constraints deployed with data validation")
        return True
        
    except Exception as e:
        try:
            conn.rollback()
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
        except:
            pass
        print(f"   ERROR: CASCADE deployment failed: {e}")
        return False

def verify_no_orphaned_data(db_path):
    """Verify no orphaned data remains"""
    print("Step 5: Verifying data integrity...")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check for orphaned tweets
        orphaned_tweets = conn.execute('''
            SELECT COUNT(*) FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        # Check for orphaned lists
        orphaned_lists = conn.execute('''
            SELECT COUNT(*) FROM twitter_list l
            LEFT JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        # Verify CASCADE constraints
        tweet_fks = conn.execute("PRAGMA foreign_key_list(tweet)").fetchall()
        list_fks = conn.execute("PRAGMA foreign_key_list(twitter_list)").fetchall()
        
        tweet_has_cascade = any('CASCADE' in str(fk) for fk in tweet_fks)
        list_has_cascade = any('CASCADE' in str(fk) for fk in list_fks)
        
        # Count final data
        accounts = conn.execute("SELECT COUNT(*) FROM twitter_account").fetchone()[0]
        tweets = conn.execute("SELECT COUNT(*) FROM tweet").fetchone()[0]
        lists = conn.execute("SELECT COUNT(*) FROM twitter_list").fetchone()[0]
        
        conn.close()
        
        print(f"   Data integrity check:")
        print(f"   - Orphaned tweets: {orphaned_tweets}")
        print(f"   - Orphaned lists: {orphaned_lists}")
        print(f"   - Tweet CASCADE: {tweet_has_cascade}")
        print(f"   - List CASCADE: {list_has_cascade}")
        print(f"   - Final counts: {accounts} accounts, {tweets} tweets, {lists} lists")
        
        success = (orphaned_tweets == 0 and orphaned_lists == 0 and 
                  tweet_has_cascade and list_has_cascade)
        
        if success:
            print("   SUCCESS: Data integrity verified, CASCADE constraints active")
        else:
            print("   ERROR: Data integrity issues remain")
        
        return success
        
    except Exception as e:
        print(f"   ERROR: Verification failed: {e}")
        return False

def main():
    """Main deployment with orphaned data cleanup"""
    print("CASCADE Deployment with Orphaned Data Cleanup")
    print("=" * 60)
    print("This version automatically cleans orphaned data to prevent FK errors")
    print("=" * 60)
    
    # Production paths
    DB_PATH = "/home/ubuntu/twitter-manager/instance/twitter_manager.db"
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False
    
    # Find existing backup
    backup_dir = os.path.dirname(DB_PATH)
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith('pre_cascade_') and f.endswith('.db')]
    
    if not backup_files:
        # Create backup if none exists
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"pre_cascade_with_cleanup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(DB_PATH, backup_path)
        print(f"Created backup: {backup_path}")
    else:
        # Use most recent backup
        latest_backup = sorted(backup_files)[-1]
        backup_path = os.path.join(backup_dir, latest_backup)
        print(f"Using existing backup: {backup_path}")
    
    # Create rollback script
    rollback_script = f'''#!/bin/bash
echo "EMERGENCY ROLLBACK: Restoring from backup"
sudo systemctl stop twitter-manager 2>/dev/null || pkill -f "python.*app.py"
cp {backup_path} {DB_PATH}
cd /home/ubuntu/twitter-manager && python app.py &
echo "Rollback completed"
'''
    
    rollback_path = os.path.join(backup_dir, 'emergency_rollback.sh')
    with open(rollback_path, 'w') as f:
        f.write(rollback_script)
    os.chmod(rollback_path, 0o755)
    
    print(f"Emergency rollback ready: {rollback_path}")
    print()
    
    # Proceed with deployment
    response = input("Proceed with CASCADE deployment with cleanup? (y/N): ").lower()
    if response != 'y':
        print("Deployment aborted")
        return False
    
    print(f"\n{'='*50}")
    print("DEPLOYING CASCADE WITH CLEANUP")
    print(f"{'='*50}")
    
    # Step 1: Clean orphaned data
    cleanup_result = cleanup_orphaned_data(DB_PATH)
    if cleanup_result is None:
        print(f"CLEANUP FAILED! Run rollback: {rollback_path}")
        return False
    
    if cleanup_result['total'] > 0:
        print(f"   INFO: Cleaned up {cleanup_result['total']} orphaned records")
    
    # Step 2: Deploy CASCADE constraints
    if not deploy_cascade_constraints_safe(DB_PATH):
        print(f"DEPLOYMENT FAILED! Run rollback: {rollback_path}")
        return False
    
    # Step 3: Verify
    if not verify_no_orphaned_data(DB_PATH):
        print(f"VERIFICATION FAILED! Run rollback: {rollback_path}")
        return False
    
    print(f"\n{'='*50}")
    print("CASCADE DEPLOYMENT SUCCESSFUL!")
    print(f"{'='*50}")
    print("✅ Orphaned data cleaned up automatically")
    print("✅ CASCADE constraints deployed")
    print("✅ Data integrity verified")
    print("✅ Account deletion now cascades safely")
    print()
    print("Your application can now be restarted!")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)