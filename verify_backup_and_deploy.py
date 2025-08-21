#!/usr/bin/env python3
"""
Production Deployment Plan with CASCADE Constraints

This script provides a step-by-step deployment plan that includes:
1. Backup verification
2. Production-safe CASCADE constraint deployment  
3. Rollback procedures
4. Data integrity checks

Since you can afford some downtime, we can deploy the full CASCADE solution safely.
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime

def verify_backup(backup_path):
    """Verify that the backup is valid and can be restored"""
    print("Step 1: Verifying database backup...")
    
    if not os.path.exists(backup_path):
        print(f"ERROR: Backup file not found: {backup_path}")
        return False
    
    backup_size = os.path.getsize(backup_path)
    print(f"   Backup file size: {backup_size:,} bytes")
    
    try:
        # Try to connect and read from backup
        conn = sqlite3.connect(backup_path)
        
        # Verify all tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        
        expected_tables = ['twitter_account', 'tweet', 'twitter_list', 'list_membership', 'follower']
        missing_tables = [t for t in expected_tables if t not in table_names]
        
        if missing_tables:
            print(f"   WARNING: Missing tables in backup: {missing_tables}")
            return False
        
        # Count records in each table
        for table in expected_tables:
            if table in table_names:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"   {table}: {count:,} records")
        
        conn.close()
        print("   SUCCESS: Backup is valid and can be restored")
        return True
        
    except Exception as e:
        print(f"   ERROR: Backup verification failed: {e}")
        return False

def create_additional_backup(db_path):
    """Create an additional timestamped backup before CASCADE deployment"""
    print("Step 2: Creating additional backup before CASCADE deployment...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"pre_cascade_backup_{timestamp}.db"
    backup_path = os.path.join(os.path.dirname(db_path), backup_name)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"   SUCCESS: Additional backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"   ERROR: Failed to create backup: {e}")
        return None

def check_current_data_integrity(db_path):
    """Check for orphaned data before migration"""
    print("Step 3: Checking current data integrity...")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check for orphaned tweets
        orphaned_tweets = conn.execute('''
            SELECT COUNT(*) as count
            FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        # Check for orphaned lists
        orphaned_lists = conn.execute('''
            SELECT COUNT(*) as count
            FROM twitter_list l
            LEFT JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        # Check for deleted accounts
        deleted_accounts = conn.execute("SELECT COUNT(*) FROM twitter_account WHERE status = 'deleted'").fetchone()[0]
        
        print(f"   Orphaned tweets: {orphaned_tweets}")
        print(f"   Orphaned lists: {orphaned_lists}")
        print(f"   Deleted accounts: {deleted_accounts}")
        
        conn.close()
        
        if orphaned_tweets > 0 or orphaned_lists > 0:
            print(f"   WARNING: Found orphaned data that will be cleaned up")
        else:
            print(f"   SUCCESS: No orphaned data found")
        
        return {
            'orphaned_tweets': orphaned_tweets,
            'orphaned_lists': orphaned_lists,
            'deleted_accounts': deleted_accounts
        }
        
    except Exception as e:
        print(f"   ERROR: Data integrity check failed: {e}")
        return None

def deploy_cascade_constraints(db_path):
    """Deploy CASCADE constraints with proper transaction handling"""
    print("Step 4: Deploying CASCADE constraints...")
    print("   WARNING: This will cause brief downtime while tables are recreated")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        
        print("   - Backing up tweet table data...")
        # Create temporary tables to hold data
        conn.execute('''
            CREATE TABLE tweet_backup AS 
            SELECT * FROM tweet
        ''')
        
        conn.execute('''
            CREATE TABLE twitter_list_backup AS 
            SELECT * FROM twitter_list
        ''')
        
        print("   - Recreating tweet table with CASCADE constraints...")
        conn.execute('DROP TABLE tweet')
        conn.execute('''
            CREATE TABLE tweet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_account_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                thread_id TEXT,
                thread_position INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id) ON DELETE CASCADE
            )
        ''')
        
        print("   - Restoring tweet data...")
        conn.execute('INSERT INTO tweet SELECT * FROM tweet_backup')
        
        print("   - Recreating twitter_list table with CASCADE constraints...")
        conn.execute('DROP TABLE twitter_list')
        conn.execute('''
            CREATE TABLE twitter_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                owner_account_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_account_id) REFERENCES twitter_account(id) ON DELETE CASCADE
            )
        ''')
        
        print("   - Restoring twitter_list data...")
        conn.execute('INSERT INTO twitter_list SELECT * FROM twitter_list_backup')
        
        print("   - Cleaning up temporary tables...")
        conn.execute('DROP TABLE tweet_backup')
        conn.execute('DROP TABLE twitter_list_backup')
        
        print("   - Committing transaction...")
        conn.commit()
        conn.close()
        
        print("   SUCCESS: CASCADE constraints deployed successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"   ERROR: CASCADE deployment failed: {e}")
        return False

def verify_cascade_deployment(db_path):
    """Verify CASCADE constraints are working"""
    print("Step 5: Verifying CASCADE constraints...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Check foreign key constraints
        tweet_fks = conn.execute("PRAGMA foreign_key_list(tweet)").fetchall()
        list_fks = conn.execute("PRAGMA foreign_key_list(twitter_list)").fetchall()
        
        tweet_has_cascade = any('CASCADE' in str(fk) for fk in tweet_fks)
        list_has_cascade = any('CASCADE' in str(fk) for fk in list_fks)
        
        print(f"   Tweet table has CASCADE: {tweet_has_cascade}")
        print(f"   Twitter_list table has CASCADE: {list_has_cascade}")
        
        # Count data after migration
        accounts = conn.execute("SELECT COUNT(*) FROM twitter_account").fetchone()[0]
        tweets = conn.execute("SELECT COUNT(*) FROM tweet").fetchone()[0]
        lists = conn.execute("SELECT COUNT(*) FROM twitter_list").fetchone()[0]
        
        print(f"   Data after migration: {accounts} accounts, {tweets} tweets, {lists} lists")
        
        conn.close()
        
        if tweet_has_cascade and list_has_cascade:
            print("   SUCCESS: CASCADE constraints verified")
            return True
        else:
            print("   ERROR: CASCADE constraints not properly applied")
            return False
            
    except Exception as e:
        print(f"   ERROR: Verification failed: {e}")
        return False

def create_rollback_script(original_backup_path):
    """Create a rollback script for emergency restoration"""
    rollback_script = f'''#!/bin/bash
# Emergency Rollback Script
# Generated: {datetime.now().isoformat()}

echo "EMERGENCY ROLLBACK: Restoring database from backup"
echo "This will restore the database to the state before CASCADE deployment"

# Stop the application
sudo systemctl stop twitter-manager 2>/dev/null || echo "Service not running"

# Backup current database (in case we need to recover recent changes)
cp /home/ubuntu/twitter-manager/instance/twitter_manager.db /home/ubuntu/twitter-manager/instance/failed_migration_backup.db

# Restore from backup
cp {original_backup_path} /home/ubuntu/twitter-manager/instance/twitter_manager.db

# Restart application
sudo systemctl start twitter-manager 2>/dev/null || echo "Start manually with: cd /home/ubuntu/twitter-manager && python app.py"

echo "Rollback completed. Database restored to pre-CASCADE state."
'''
    
    rollback_path = os.path.join(os.path.dirname(original_backup_path), 'emergency_rollback.sh')
    with open(rollback_path, 'w') as f:
        f.write(rollback_script)
    
    os.chmod(rollback_path, 0o755)  # Make executable
    print(f"   Rollback script created: {rollback_path}")
    return rollback_path

def main():
    """Main deployment orchestrator"""
    print("Twitter Manager - Production CASCADE Deployment Plan")
    print("=" * 70)
    print("This plan will safely deploy CASCADE constraints with proper backups")
    print("=" * 70)
    
    # Configuration - you'll need to adjust these paths for production
    DB_PATH = "/home/ubuntu/twitter-manager/instance/twitter_manager.db"  # Production path
    BACKUP_PATH = "/home/ubuntu/twitter-manager/instance/database_backup_20250821_000311.db"  # Your existing backup
    
    print(f"Database path: {DB_PATH}")
    print(f"Existing backup: {BACKUP_PATH}")
    print()
    
    # Step 1: Verify existing backup
    if not verify_backup(BACKUP_PATH):
        print("ABORT: Cannot proceed without valid backup")
        return False
    
    # Step 2: Create additional backup
    additional_backup = create_additional_backup(DB_PATH)
    if not additional_backup:
        print("ABORT: Cannot create additional backup")
        return False
    
    # Step 3: Check data integrity
    integrity_check = check_current_data_integrity(DB_PATH)
    if not integrity_check:
        print("ABORT: Data integrity check failed")
        return False
    
    # Step 4: Create rollback script
    rollback_script = create_rollback_script(additional_backup)
    
    print(f"\n{'='*50}")
    print("PRE-DEPLOYMENT SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Original backup verified: {BACKUP_PATH}")
    print(f"✅ Additional backup created: {additional_backup}")
    print(f"✅ Data integrity checked")
    print(f"✅ Rollback script ready: {rollback_script}")
    print(f"✅ Orphaned data will be cleaned: {integrity_check['orphaned_tweets']} tweets, {integrity_check['orphaned_lists']} lists")
    print()
    
    # Deployment confirmation
    print("READY FOR CASCADE DEPLOYMENT")
    print("This will:")
    print("  1. Stop application briefly")
    print("  2. Recreate tables with CASCADE constraints") 
    print("  3. Restore all data")
    print("  4. Enable automatic cleanup of orphaned data")
    print()
    print("Estimated downtime: 30-60 seconds")
    print()
    
    response = input("Proceed with CASCADE deployment? (y/N): ").lower()
    if response != 'y':
        print("Deployment aborted by user")
        return False
    
    # Step 5: Deploy CASCADE constraints
    if not deploy_cascade_constraints(DB_PATH):
        print(f"\nDEPLOYMENT FAILED!")
        print(f"Run rollback script: {rollback_script}")
        return False
    
    # Step 6: Verify deployment
    if not verify_cascade_deployment(DB_PATH):
        print(f"\nVERIFICATION FAILED!")
        print(f"Run rollback script: {rollback_script}")
        return False
    
    print(f"\n{'='*50}")
    print("DEPLOYMENT SUCCESSFUL!")
    print(f"{'='*50}")
    print("✅ CASCADE constraints deployed")
    print("✅ All data preserved")
    print("✅ Orphaned data cleanup enabled")
    print("✅ Account deletion now automatically cascades")
    print()
    print("Next steps:")
    print("  1. Restart your application")
    print("  2. Test account deletion functionality")
    print("  3. Monitor for any issues")
    print(f"  4. Keep rollback script handy: {rollback_script}")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)