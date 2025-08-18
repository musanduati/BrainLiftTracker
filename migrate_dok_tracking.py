#!/usr/bin/env python3
"""
DOK Tracking Migration Script

This script safely adds DOK tracking columns and migrates historical data.
Designed for production use on Lightsail instance.

Usage:
    python migrate_dok_tracking.py [--dry-run] [--backup]

Options:
    --dry-run    Show what would be done without making changes
    --backup     Create database backup before migration (recommended)
"""

import sqlite3
import os
import sys
import re
import shutil
from datetime import datetime
from pathlib import Path

def get_db_path():
    """Get the database path (same logic as main app)"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'twitter_manager.db')

def backup_database(db_path):
    """Create a backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"SUCCESS: Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"ERROR: Backup failed: {e}")
        return None

def add_dok_columns(conn, dry_run=False):
    """Add DOK tracking columns to tweet table"""
    print("\n1. Adding DOK tracking columns...")
    
    columns_to_add = [
        ("dok_type", "VARCHAR(10)"),
        ("change_type", "VARCHAR(10)")
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            if dry_run:
                print(f"   [DRY-RUN] Would add column: {column_name} {column_type}")
            else:
                conn.execute(f'ALTER TABLE tweet ADD COLUMN {column_name} {column_type}')
                print(f"   SUCCESS: Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"   INFO: Column {column_name} already exists, skipping")
            else:
                print(f"   ERROR: Error adding {column_name}: {e}")
                raise

def parse_dok_metadata(tweet_content):
    """Parse DOK metadata from tweet content (same as main app)"""
    # Pattern to match optional emoji + ADDED/DELETED/UPDATED: DOK3/DOK4: at start of tweet
    # Handles: "ADDED: DOK3:", "🟢 ADDED: DOK4:", "❌ DELETED: DOK3:", "🔄 UPDATED: DOK4:", etc.
    pattern = r'^(?:[🟢❌🔄]\s*)?(ADDED|DELETED|UPDATED):\s+(DOK[34]):'
    match = re.match(pattern, tweet_content.strip())
    if match:
        change_type = match.group(1)  # ADDED, DELETED, or UPDATED
        dok_type = match.group(2)     # DOK3 or DOK4
        return dok_type, change_type
    return None, None

def migrate_historical_data(conn, dry_run=False):
    """Migrate historical tweet data to include DOK metadata"""
    print("\n2. Analyzing historical tweets...")
    
    # Get tweets that are thread starters (position 0 or 1) or standalone tweets
    cursor = conn.execute('''
        SELECT id, content, thread_id, thread_position
        FROM tweet 
        WHERE (thread_position IN (0, 1) OR thread_position IS NULL OR thread_id IS NULL)
        AND (dok_type IS NULL OR change_type IS NULL)
        ORDER BY id
    ''')
    
    tweets_to_process = cursor.fetchall()
    print(f"   Found {len(tweets_to_process)} potential DOK tweets to process")
    
    if len(tweets_to_process) == 0:
        print("   No tweets need DOK metadata processing")
        return
    
    # Process each tweet
    updates_count = 0
    for tweet in tweets_to_process:
        tweet_id, content, thread_id, thread_position = tweet
        dok_type, change_type = parse_dok_metadata(content)
        
        if dok_type and change_type:
            if dry_run:
                print(f"   [DRY-RUN] Tweet {tweet_id}: {change_type} {dok_type}")
            else:
                # Update the first tweet
                conn.execute('''
                    UPDATE tweet 
                    SET dok_type = ?, change_type = ? 
                    WHERE id = ?
                ''', (dok_type, change_type, tweet_id))
                
                # If this is a thread, propagate to all tweets in the thread
                if thread_id:
                    conn.execute('''
                        UPDATE tweet 
                        SET dok_type = ?, change_type = ? 
                        WHERE thread_id = ? AND id != ?
                    ''', (dok_type, change_type, thread_id, tweet_id))
                
                updates_count += 1
    
    if not dry_run:
        conn.commit()
        print(f"   SUCCESS: Updated {updates_count} tweet records with DOK metadata")
    else:
        print(f"   [DRY-RUN] Would update {updates_count} tweet records")

def verify_migration(conn):
    """Verify the migration was successful"""
    print("\n3. Verifying migration...")
    
    # Check column existence
    cursor = conn.execute("PRAGMA table_info(tweet)")
    columns = [row[1] for row in cursor.fetchall()]
    
    required_columns = ['dok_type', 'change_type']
    for col in required_columns:
        if col in columns:
            print(f"   SUCCESS: Column {col} exists")
        else:
            print(f"   ERROR: Column {col} missing!")
            return False
    
    # Check data
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total,
            COUNT(dok_type) as with_dok_type,
            COUNT(change_type) as with_change_type
        FROM tweet
    ''')
    
    stats = cursor.fetchone()
    print(f"   Total tweets: {stats[0]}")
    print(f"   With DOK type: {stats[1]}")
    print(f"   With change type: {stats[2]}")
    
    # Sample some DOK tweets
    cursor = conn.execute('''
        SELECT dok_type, change_type, COUNT(*) as count
        FROM tweet 
        WHERE dok_type IS NOT NULL
        GROUP BY dok_type, change_type
        ORDER BY count DESC
    ''')
    
    dok_stats = cursor.fetchall()
    if dok_stats:
        print("   DOK breakdown:")
        for dok_type, change_type, count in dok_stats:
            print(f"     {change_type} {dok_type}: {count} tweets")
    else:
        print("   No DOK metadata found in tweets")
    
    return True

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate DOK tracking for Twitter Manager')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--backup', action='store_true',
                       help='Create database backup before migration')
    
    args = parser.parse_args()
    
    # Get database path
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at: {db_path}")
        sys.exit(1)
    
    print(f"DOK Tracking Migration")
    print(f"Database: {db_path}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE MIGRATION'}")
    
    # Create backup if requested
    if args.backup and not args.dry_run:
        backup_path = backup_database(db_path)
        if not backup_path:
            print("ERROR: Backup failed, aborting migration for safety")
            sys.exit(1)
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        print("SUCCESS: Connected to database")
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        sys.exit(1)
    
    try:
        # Run migration steps
        add_dok_columns(conn, args.dry_run)
        migrate_historical_data(conn, args.dry_run)
        
        if not args.dry_run:
            verify_migration(conn)
            print("\nSUCCESS: Migration completed successfully!")
        else:
            print("\nSUCCESS: Dry-run completed. Use without --dry-run to apply changes.")
            
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        if not args.dry_run:
            conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()