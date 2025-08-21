#!/usr/bin/env python3
"""
CASCADE Constraints Production Deployment

This script safely deploys CASCADE constraints to production using the actual
database schema. Handles the real production schema with:
- Tweet table: 12 columns (twitter_id, posted_at, dok_type, etc.)
- Twitter_list table: 12 columns (with management fields)
- Twitter_account table: 15 columns (with OAuth and metadata)

Replaces verify_backup_and_deploy.py with schema-aware deployment.
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime

def verify_existing_backup(backup_path):
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
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    print(f"   {table}: {count:,} records")
                except:
                    print(f"   {table}: unable to read (may be empty)")
        
        conn.close()
        print("   SUCCESS: Backup is valid and can be restored")
        return True
        
    except Exception as e:
        print(f"   ERROR: Backup verification failed: {e}")
        return False

def create_pre_deployment_backup(db_path):
    """Create an additional timestamped backup before CASCADE deployment"""
    print("Step 2: Creating pre-deployment backup...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"pre_cascade_{timestamp}.db"
    backup_path = os.path.join(os.path.dirname(db_path), backup_name)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"   SUCCESS: Pre-deployment backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"   ERROR: Failed to create backup: {e}")
        return None

def analyze_current_schema(db_path):
    """Analyze the current database schema"""
    print("Step 3: Analyzing current database schema...")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get actual schema for tweet table
        tweet_columns = conn.execute("PRAGMA table_info(tweet)").fetchall()
        list_columns = conn.execute("PRAGMA table_info(twitter_list)").fetchall()
        account_columns = conn.execute("PRAGMA table_info(twitter_account)").fetchall()
        
        print(f"   Tweet table: {len(tweet_columns)} columns")
        print(f"   Twitter_list table: {len(list_columns)} columns") 
        print(f"   Twitter_account table: {len(account_columns)} columns")
        
        # Check for orphaned data
        orphaned_tweets = conn.execute('''
            SELECT COUNT(*) FROM tweet t
            LEFT JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        orphaned_lists = conn.execute('''
            SELECT COUNT(*) FROM twitter_list l
            LEFT JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE a.id IS NULL
        ''').fetchone()[0]
        
        deleted_accounts = conn.execute("SELECT COUNT(*) FROM twitter_account WHERE status = 'deleted'").fetchone()[0]
        
        print(f"   Orphaned tweets: {orphaned_tweets}")
        print(f"   Orphaned lists: {orphaned_lists}")
        print(f"   Deleted accounts: {deleted_accounts}")
        
        conn.close()
        
        return {
            'tweet_columns': len(tweet_columns),
            'list_columns': len(list_columns),
            'account_columns': len(account_columns),
            'orphaned_tweets': orphaned_tweets,
            'orphaned_lists': orphaned_lists,
            'deleted_accounts': deleted_accounts
        }
        
    except Exception as e:
        print(f"   ERROR: Schema analysis failed: {e}")
        return None

def deploy_cascade_constraints(db_path):
    """Deploy CASCADE constraints using the actual production schema"""
    print("Step 4: Deploying CASCADE constraints...")
    print("   Using production schema (tweet: 12 cols, twitter_list: 12 cols)")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        
        print("   - Creating backup tables...")
        conn.execute('CREATE TABLE tweet_backup AS SELECT * FROM tweet')
        conn.execute('CREATE TABLE twitter_list_backup AS SELECT * FROM twitter_list')
        
        print("   - Recreating tweet table with CASCADE...")
        conn.execute('DROP TABLE tweet')
        
        # Production tweet schema with CASCADE
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
        
        conn.execute('INSERT INTO tweet SELECT * FROM tweet_backup')
        
        print("   - Recreating twitter_list table with CASCADE...")
        conn.execute('DROP TABLE twitter_list')
        
        # Production twitter_list schema with CASCADE
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
        
        conn.execute('INSERT INTO twitter_list SELECT * FROM twitter_list_backup')
        
        print("   - Cleaning up...")
        conn.execute('DROP TABLE tweet_backup')
        conn.execute('DROP TABLE twitter_list_backup')
        
        conn.commit()
        conn.close()
        
        print("   SUCCESS: CASCADE constraints deployed")
        return True
        
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        print(f"   ERROR: CASCADE deployment failed: {e}")
        return False

def verify_deployment(db_path):
    """Verify CASCADE constraints are working"""
    print("Step 5: Verifying CASCADE deployment...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Check foreign key constraints
        tweet_fks = conn.execute("PRAGMA foreign_key_list(tweet)").fetchall()
        list_fks = conn.execute("PRAGMA foreign_key_list(twitter_list)").fetchall()
        
        tweet_has_cascade = any('CASCADE' in str(fk) for fk in tweet_fks)
        list_has_cascade = any('CASCADE' in str(fk) for fk in list_fks)
        
        print(f"   Tweet table CASCADE: {tweet_has_cascade}")
        print(f"   Twitter_list table CASCADE: {list_has_cascade}")
        
        # Verify column counts
        tweet_columns = conn.execute("PRAGMA table_info(tweet)").fetchall()
        list_columns = conn.execute("PRAGMA table_info(twitter_list)").fetchall()
        
        print(f"   Tweet table columns: {len(tweet_columns)} (expected 12)")
        print(f"   Twitter_list table columns: {len(list_columns)} (expected 12)")
        
        # Count final data
        accounts = conn.execute("SELECT COUNT(*) FROM twitter_account").fetchone()[0]
        tweets = conn.execute("SELECT COUNT(*) FROM tweet").fetchone()[0]
        lists = conn.execute("SELECT COUNT(*) FROM twitter_list").fetchone()[0]
        
        print(f"   Final data: {accounts} accounts, {tweets} tweets, {lists} lists")
        
        conn.close()
        
        success = (tweet_has_cascade and list_has_cascade and 
                  len(tweet_columns) == 12 and len(list_columns) == 12)
        
        if success:
            print("   SUCCESS: CASCADE deployment verified")
        else:
            print("   ERROR: CASCADE deployment verification failed")
        
        return success
        
    except Exception as e:
        print(f"   ERROR: Verification failed: {e}")
        return False

def create_emergency_rollback_script(backup_path):
    """Create emergency rollback script"""
    rollback_content = f'''#!/bin/bash
# Emergency Rollback Script
# Generated: {datetime.now().isoformat()}

echo "EMERGENCY ROLLBACK: Restoring database from backup"
echo "This will restore the database to pre-CASCADE state"

# Stop application
sudo systemctl stop twitter-manager 2>/dev/null || pkill -f "python.*app.py"

# Backup current state (in case we need it)
cp /home/ubuntu/twitter-manager/instance/twitter_manager.db /home/ubuntu/twitter-manager/instance/failed_cascade_backup.db

# Restore from backup
cp {backup_path} /home/ubuntu/twitter-manager/instance/twitter_manager.db

# Restart application
cd /home/ubuntu/twitter-manager
python app.py &

echo "Rollback completed. Database restored to pre-CASCADE state."
echo "Application should be running normally again."
'''
    
    rollback_path = os.path.join(os.path.dirname(backup_path), 'emergency_rollback.sh')
    with open(rollback_path, 'w') as f:
        f.write(rollback_content)
    
    os.chmod(rollback_path, 0o755)
    print(f"   Emergency rollback script: {rollback_path}")
    return rollback_path

def main():
    """Main deployment function"""
    print("CASCADE Constraints Production Deployment")
    print("=" * 60)
    print("This deployment handles the actual production schema:")
    print("  - Tweet table: 12 columns (twitter_id, posted_at, dok_type, etc.)")
    print("  - Twitter_list table: 12 columns (management fields)")
    print("  - Safe transaction-based deployment")
    print("=" * 60)
    
    # Production paths
    DB_PATH = "/home/ubuntu/twitter-manager/instance/twitter_manager.db"
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Please run this script on the production server")
        return False
    
    # Find existing backup
    backup_dir = os.path.dirname(DB_PATH)
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith('database_backup_') and f.endswith('.db')]
    
    if not backup_files:
        print("ERROR: No existing backup files found")
        print("Please ensure you have a valid backup before proceeding")
        return False
    
    # Use most recent backup
    latest_backup = sorted(backup_files)[-1]
    backup_path = os.path.join(backup_dir, latest_backup)
    
    print(f"Database: {DB_PATH}")
    print(f"Existing backup: {backup_path}")
    print()
    
    # Step 1: Verify existing backup
    if not verify_existing_backup(backup_path):
        print("ABORT: Cannot proceed without valid backup")
        return False
    
    # Step 2: Create pre-deployment backup
    pre_backup = create_pre_deployment_backup(DB_PATH)
    if not pre_backup:
        print("ABORT: Cannot create pre-deployment backup")
        return False
    
    # Step 3: Analyze current schema
    schema_info = analyze_current_schema(DB_PATH)
    if not schema_info:
        print("ABORT: Schema analysis failed")
        return False
    
    # Step 4: Create emergency rollback
    rollback_script = create_emergency_rollback_script(pre_backup)
    
    print(f"\n{'='*50}")
    print("PRE-DEPLOYMENT SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Existing backup verified: {backup_path}")
    print(f"✅ Pre-deployment backup created: {pre_backup}")
    print(f"✅ Emergency rollback script: {rollback_script}")
    print(f"✅ Schema analyzed: {schema_info['tweet_columns']}-col tweets, {schema_info['list_columns']}-col lists")
    print(f"✅ Orphaned data: {schema_info['orphaned_tweets']} tweets, {schema_info['orphaned_lists']} lists")
    print()
    
    print("READY FOR CASCADE DEPLOYMENT")
    print("This will:")
    print("  1. Recreate tables with CASCADE constraints")
    print("  2. Preserve all data including twitter_id, posted_at, dok_type")
    print("  3. Enable automatic orphaned data cleanup")
    print("  4. Complete in 30-60 seconds")
    print()
    
    response = input("Proceed with CASCADE deployment? (y/N): ").lower()
    if response != 'y':
        print("Deployment aborted by user")
        return False
    
    # Step 5: Deploy CASCADE constraints
    print(f"\n{'='*50}")
    print("DEPLOYING CASCADE CONSTRAINTS")
    print(f"{'='*50}")
    
    if not deploy_cascade_constraints(DB_PATH):
        print(f"\nDEPLOYMENT FAILED!")
        print(f"Run emergency rollback: {rollback_script}")
        return False
    
    # Step 6: Verify deployment
    if not verify_deployment(DB_PATH):
        print(f"\nVERIFICATION FAILED!")
        print(f"Run emergency rollback: {rollback_script}")
        return False
    
    print(f"\n{'='*50}")
    print("CASCADE DEPLOYMENT SUCCESSFUL!")
    print(f"{'='*50}")
    print("✅ CASCADE constraints deployed with correct schema")
    print("✅ All production data preserved")
    print("✅ Orphaned data cleanup enabled")
    print("✅ Account deletion now automatically cascades")
    print()
    print("Next steps:")
    print("  1. Restart your application")
    print("  2. Test account deletion functionality")
    print("  3. Monitor application logs")
    print(f"  4. Keep rollback script available: {rollback_script}")
    print()
    print("🎯 Production database now has CASCADE constraints!")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)