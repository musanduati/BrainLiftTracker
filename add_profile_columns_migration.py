#!/usr/bin/env python3
"""
Migration script to add display_name and profile_picture columns to twitter_account table.
Run this on your production server to update the database schema.
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Add display_name and profile_picture columns to twitter_account table"""
    
    # Get database path
    db_path = Path(__file__).parent / 'instance' / 'twitter_manager.db'
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    print(f"Migrating database at: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(twitter_account)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_performed = []
        
        # Add display_name column if it doesn't exist
        if 'display_name' not in columns:
            cursor.execute('ALTER TABLE twitter_account ADD COLUMN display_name TEXT')
            migrations_performed.append('display_name')
            print("+ Added display_name column to twitter_account table")
        else:
            print("- display_name column already exists")
        
        # Add profile_picture column if it doesn't exist
        if 'profile_picture' not in columns:
            cursor.execute('ALTER TABLE twitter_account ADD COLUMN profile_picture TEXT')
            migrations_performed.append('profile_picture')
            print("+ Added profile_picture column to twitter_account table")
        else:
            print("- profile_picture column already exists")
        
        # Commit changes
        if migrations_performed:
            conn.commit()
            print(f"\n[SUCCESS] Migration completed successfully! Added columns: {', '.join(migrations_performed)}")
        else:
            print("\n[INFO] No migration needed - all columns already exist")
        
        # Show current schema
        print("\nCurrent twitter_account table schema:")
        cursor.execute("PRAGMA table_info(twitter_account)")
        for col in cursor.fetchall():
            print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Twitter Manager Database Migration ===")
    print("Adding profile sync support columns...\n")
    
    success = migrate_database()
    
    if success:
        print("\n[SUCCESS] Migration completed successfully!")
        print("You can now use the /api/v1/accounts/sync-profiles endpoint")
    else:
        print("\n[WARNING] Migration failed. Please check the error messages above.")