#!/usr/bin/env python
"""Import Workflowy URLs from CSV files and update database"""

import csv
import sqlite3
import os
from app.core.config import Config

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def import_workflowy_urls():
    """Import Workflowy URLs from CSV files"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Track statistics
    total_found = 0
    total_updated = 0
    not_found = []
    
    # CSV files to import
    csv_files = [
        'SuperBuilders.csv',
        'Academics.csv'
    ]
    
    # Process each CSV file
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"Warning: {csv_file} not found, skipping...")
            continue
            
        print(f"\nProcessing {csv_file}...")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Get the Workflowy URL and Twitter account
                if csv_file == 'SuperBuilders.csv':
                    workflowy_url = row.get('BrainLift', '').strip()
                    twitter_account = row.get('Twitter Account', '').strip()
                else:  # Academics.csv
                    workflowy_url = row.get('Sub-Map BrainLift', '').strip()
                    twitter_account = row.get('Twitter Account', '').strip()
                
                if not workflowy_url or not twitter_account:
                    continue
                
                # Remove @ from Twitter account if present
                username = twitter_account.lstrip('@')
                
                total_found += 1
                
                # Check if account exists in database
                cursor.execute(
                    'SELECT id, username, workflowy_url FROM twitter_account WHERE username = ?',
                    (username,)
                )
                account = cursor.fetchone()
                
                if account:
                    # Update the workflowy_url
                    cursor.execute(
                        'UPDATE twitter_account SET workflowy_url = ? WHERE username = ?',
                        (workflowy_url, username)
                    )
                    total_updated += 1
                    print(f"  [OK] Updated @{username} with Workflowy URL")
                else:
                    not_found.append(f"@{username}")
                    print(f"  [NOT FOUND] Account @{username} not found in database")
    
    # Commit changes
    conn.commit()
    
    # Print summary
    print("\n" + "="*50)
    print("IMPORT SUMMARY")
    print("="*50)
    print(f"Total mappings found in CSV files: {total_found}")
    print(f"Accounts updated with Workflowy URLs: {total_updated}")
    print(f"Accounts not found in database: {len(not_found)}")
    
    if not_found:
        print("\nAccounts not found in database:")
        for username in not_found[:10]:  # Show first 10
            print(f"  - {username}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")
    
    conn.close()
    print("\nImport complete!")

if __name__ == "__main__":
    print("Importing Workflowy URLs from CSV files...")
    print("This will update the database with Workflowy URLs for matching Twitter accounts.")
    print()
    
    # Check for command line argument to skip confirmation
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("Running in auto mode...")
    else:
        # Confirm before proceeding
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Import cancelled.")
            exit(0)
    
    import_workflowy_urls()