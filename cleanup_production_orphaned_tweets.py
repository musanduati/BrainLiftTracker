#!/usr/bin/env python3
"""
Production Orphaned Tweets Cleanup Script
This script safely removes tweets from deleted accounts on the production server.
"""

import sqlite3
import os
import shutil
from datetime import datetime
from typing import Dict, List, Tuple

def create_backup(db_path: str) -> str:
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.cleanup_backup_{timestamp}"
    
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    return backup_path

def analyze_orphaned_data(db_path: str) -> Dict:
    """Analyze orphaned tweets and related data"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    analysis = {
        'orphaned_tweets': [],
        'deleted_accounts': [],
        'summary': {}
    }
    
    # Find deleted accounts
    deleted_accounts = conn.execute("""
        SELECT id, username, status, created_at
        FROM twitter_account 
        WHERE status = 'deleted'
        ORDER BY username
    """).fetchall()
    
    analysis['deleted_accounts'] = [dict(row) for row in deleted_accounts]
    
    # Find orphaned tweets from deleted accounts
    orphaned_tweets = conn.execute("""
        SELECT 
            t.id,
            t.twitter_account_id,
            t.content,
            t.status,
            t.thread_id,
            t.created_at,
            a.username,
            a.status as account_status
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE a.status = 'deleted'
        ORDER BY a.username, t.created_at
    """).fetchall()
    
    analysis['orphaned_tweets'] = [dict(row) for row in orphaned_tweets]
    
    # Summary statistics
    analysis['summary'] = {
        'total_deleted_accounts': len(analysis['deleted_accounts']),
        'total_orphaned_tweets': len(analysis['orphaned_tweets']),
        'orphaned_by_status': {},
        'orphaned_by_account': {}
    }
    
    # Group by tweet status
    for tweet in analysis['orphaned_tweets']:
        status = tweet['status']
        analysis['summary']['orphaned_by_status'][status] = analysis['summary']['orphaned_by_status'].get(status, 0) + 1
    
    # Group by account
    for tweet in analysis['orphaned_tweets']:
        username = tweet['username']
        analysis['summary']['orphaned_by_account'][username] = analysis['summary']['orphaned_by_account'].get(username, 0) + 1
    
    conn.close()
    return analysis

def cleanup_orphaned_tweets(db_path: str, dry_run: bool = True) -> Dict:
    """Clean up orphaned tweets from deleted accounts"""
    conn = sqlite3.connect(db_path)
    
    cleanup_results = {
        'tweets_deleted': 0,
        'accounts_affected': set(),
        'errors': []
    }
    
    try:
        if not dry_run:
            # Get affected accounts before deletion for reporting
            affected_accounts = conn.execute("""
                SELECT DISTINCT a.username 
                FROM twitter_account a
                JOIN tweet t ON a.id = t.twitter_account_id
                WHERE a.status = 'deleted'
            """).fetchall()
            
            cleanup_results['accounts_affected'] = {row[0] for row in affected_accounts}
            
            # Delete orphaned tweets
            cursor = conn.execute("""
                DELETE FROM tweet 
                WHERE twitter_account_id IN (
                    SELECT id FROM twitter_account WHERE status = 'deleted'
                )
            """)
            cleanup_results['tweets_deleted'] = cursor.rowcount
            
            conn.commit()
            print(f"Deleted {cleanup_results['tweets_deleted']} orphaned tweets")
        else:
            # Count what would be deleted
            count_result = conn.execute("""
                SELECT COUNT(*) as count
                FROM tweet 
                WHERE twitter_account_id IN (
                    SELECT id FROM twitter_account WHERE status = 'deleted'
                )
            """).fetchone()
            
            cleanup_results['tweets_deleted'] = count_result[0]
            print(f"DRY RUN: Would delete {cleanup_results['tweets_deleted']} orphaned tweets")
        
    except Exception as e:
        cleanup_results['errors'].append(str(e))
        conn.rollback()
    finally:
        conn.close()
    
    return cleanup_results

def verify_cleanup(db_path: str) -> Dict:
    """Verify the cleanup was successful"""
    conn = sqlite3.connect(db_path)
    
    verification = {
        'remaining_orphaned_tweets': 0,
        'total_active_tweets': 0,
        'total_pending_tweets': 0,
        'total_accounts': 0,
        'deleted_accounts': 0
    }
    
    # Check remaining orphaned tweets
    remaining = conn.execute("""
        SELECT COUNT(*) as count
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE a.status = 'deleted'
    """).fetchone()
    
    verification['remaining_orphaned_tweets'] = remaining[0]
    
    # Check total active tweets
    active_tweets = conn.execute("""
        SELECT COUNT(*) as count
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE a.status != 'deleted'
    """).fetchone()
    
    verification['total_active_tweets'] = active_tweets[0]
    
    # Check pending tweets from active accounts
    pending_tweets = conn.execute("""
        SELECT COUNT(*) as count
        FROM tweet t
        JOIN twitter_account a ON t.twitter_account_id = a.id
        WHERE a.status != 'deleted' AND t.status = 'pending'
    """).fetchone()
    
    verification['total_pending_tweets'] = pending_tweets[0]
    
    # Account statistics
    account_stats = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'deleted' THEN 1 ELSE 0 END) as deleted
        FROM twitter_account
    """).fetchone()
    
    verification['total_accounts'] = account_stats[0]
    verification['deleted_accounts'] = account_stats[1]
    
    conn.close()
    return verification

def main():
    """Main cleanup orchestration"""
    # Production database path
    db_path = '/home/ubuntu/twitter-manager/instance/twitter_manager.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print("Analyzing orphaned data...")
    analysis = analyze_orphaned_data(db_path)
    
    print("\n" + "="*60)
    print("PRODUCTION ORPHANED DATA ANALYSIS")
    print("="*60)
    print(f"Deleted accounts: {analysis['summary']['total_deleted_accounts']}")
    print(f"Orphaned tweets: {analysis['summary']['total_orphaned_tweets']}")
    
    if analysis['summary']['orphaned_by_status']:
        print("\nOrphaned tweets by status:")
        for status, count in analysis['summary']['orphaned_by_status'].items():
            print(f"  {status}: {count}")
    
    if analysis['summary']['orphaned_by_account']:
        print(f"\nOrphaned tweets by account (top 10):")
        sorted_accounts = sorted(
            analysis['summary']['orphaned_by_account'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        for username, count in sorted_accounts:
            print(f"  {username}: {count} tweets")
    
    if analysis['summary']['total_orphaned_tweets'] == 0:
        print("\nNo orphaned tweets found. Database is clean!")
        return
    
    print(f"\nFound {analysis['summary']['total_orphaned_tweets']} orphaned tweets from {analysis['summary']['total_deleted_accounts']} deleted accounts")
    
    # Dry run first
    print("\n" + "="*60)
    print("DRY RUN")
    print("="*60)
    dry_run_results = cleanup_orphaned_tweets(db_path, dry_run=True)
    
    if dry_run_results['errors']:
        print("Errors during dry run:")
        for error in dry_run_results['errors']:
            print(f"  {error}")
        return
    
    # Ask for confirmation
    print(f"\nThis will permanently delete {dry_run_results['tweets_deleted']} orphaned tweets.")
    print("This will allow the automation to process pending tweets from active accounts only.")
    confirm = input("Proceed with cleanup? (yes/no): ").lower().strip()
    
    if confirm != 'yes':
        print("Cleanup cancelled by user")
        return
    
    # Create backup
    print("\n" + "="*60)
    print("BACKUP & CLEANUP")
    print("="*60)
    backup_path = create_backup(db_path)
    
    # Perform actual cleanup
    print("Performing cleanup...")
    cleanup_results = cleanup_orphaned_tweets(db_path, dry_run=False)
    
    if cleanup_results['errors']:
        print("Errors during cleanup:")
        for error in cleanup_results['errors']:
            print(f"  {error}")
        return
    
    # Verify cleanup
    print("\nVerifying cleanup...")
    verification = verify_cleanup(db_path)
    
    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60)
    print(f"Deleted {cleanup_results['tweets_deleted']} orphaned tweets")
    print(f"Backup saved: {backup_path}")
    print(f"Remaining orphaned tweets: {verification['remaining_orphaned_tweets']}")
    print(f"Total active tweets: {verification['total_active_tweets']}")
    print(f"Total pending tweets from active accounts: {verification['total_pending_tweets']}")
    print(f"Total accounts: {verification['total_accounts']} ({verification['deleted_accounts']} deleted)")
    
    if verification['remaining_orphaned_tweets'] > 0:
        print(f"Warning: {verification['remaining_orphaned_tweets']} orphaned tweets still remain")
    else:
        print("All orphaned tweets successfully cleaned up!")
        print("Automation should now process pending tweets from active accounts only.")

if __name__ == '__main__':
    main()