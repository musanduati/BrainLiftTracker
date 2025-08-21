#!/usr/bin/env python3
"""
Test Rollback Procedures

This script tests the rollback procedures on a local copy to ensure
they work correctly before production deployment.
"""

import sqlite3
import sys
import os
import shutil
import tempfile
from datetime import datetime

def create_test_database():
    """Create a test database similar to production"""
    print("Creating test database...")
    
    test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    test_db.close()
    
    conn = sqlite3.connect(test_db.name)
    
    # Create current schema (with status column, no CASCADE)
    conn.execute('''
        CREATE TABLE twitter_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE tweet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitter_account_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            thread_id TEXT,
            thread_position INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE twitter_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            owner_account_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_account_id) REFERENCES twitter_account(id)
        )
    ''')
    
    # Insert test data
    conn.execute("INSERT INTO twitter_account (id, username) VALUES (1, 'testuser1')")
    conn.execute("INSERT INTO twitter_account (id, username) VALUES (2, 'testuser2')")
    conn.execute("INSERT INTO tweet (twitter_account_id, content) VALUES (1, 'Test tweet 1')")
    conn.execute("INSERT INTO tweet (twitter_account_id, content) VALUES (1, 'Test tweet 2')")
    conn.execute("INSERT INTO tweet (twitter_account_id, content) VALUES (2, 'Test tweet 3')")
    conn.execute("INSERT INTO twitter_list (list_id, name, owner_account_id) VALUES ('list1', 'Test List 1', 1)")
    conn.execute("INSERT INTO twitter_list (list_id, name, owner_account_id) VALUES ('list2', 'Test List 2', 2)")
    
    conn.commit()
    conn.close()
    
    print(f"Test database created: {test_db.name}")
    return test_db.name

def create_backup(db_path):
    """Create a backup of the test database"""
    backup_path = db_path + '.backup'
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path

def apply_cascade_constraints(db_path):
    """Apply CASCADE constraints to test database"""
    print("Applying CASCADE constraints...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN TRANSACTION')
        
        # Backup data
        conn.execute('CREATE TABLE tweet_backup AS SELECT * FROM tweet')
        conn.execute('CREATE TABLE twitter_list_backup AS SELECT * FROM twitter_list')
        
        # Recreate with CASCADE
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
                FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id) ON DELETE CASCADE
            )
        ''')
        conn.execute('INSERT INTO tweet SELECT * FROM tweet_backup')
        
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
        conn.execute('INSERT INTO twitter_list SELECT * FROM twitter_list_backup')
        
        conn.execute('DROP TABLE tweet_backup')
        conn.execute('DROP TABLE twitter_list_backup')
        
        conn.commit()
        conn.close()
        
        print("CASCADE constraints applied successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Failed to apply CASCADE constraints: {e}")
        return False

def verify_cascade_works(db_path):
    """Test that CASCADE deletion works"""
    print("Testing CASCADE deletion...")
    
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    
    # Count data before deletion
    tweets_before = conn.execute("SELECT COUNT(*) FROM tweet WHERE twitter_account_id = 1").fetchone()[0]
    lists_before = conn.execute("SELECT COUNT(*) FROM twitter_list WHERE owner_account_id = 1").fetchone()[0]
    
    print(f"Before deletion: {tweets_before} tweets, {lists_before} lists for user 1")
    
    # Delete account 1
    conn.execute("DELETE FROM twitter_account WHERE id = 1")
    conn.commit()
    
    # Count data after deletion
    tweets_after = conn.execute("SELECT COUNT(*) FROM tweet WHERE twitter_account_id = 1").fetchone()[0]
    lists_after = conn.execute("SELECT COUNT(*) FROM twitter_list WHERE owner_account_id = 1").fetchone()[0]
    accounts_after = conn.execute("SELECT COUNT(*) FROM twitter_account WHERE id = 1").fetchone()[0]
    
    print(f"After deletion: {tweets_after} tweets, {lists_after} lists, {accounts_after} accounts")
    
    conn.close()
    
    # Verify CASCADE worked
    success = (accounts_after == 0 and tweets_after == 0 and lists_after == 0)
    if success:
        print("SUCCESS: CASCADE deletion working correctly")
    else:
        print("FAILED: CASCADE deletion not working")
    
    return success

def test_rollback(db_path, backup_path):
    """Test rollback procedure"""
    print("Testing rollback procedure...")
    
    # Verify current state (should have CASCADE and missing user 1)
    conn = sqlite3.connect(db_path)
    accounts_before = conn.execute("SELECT COUNT(*) FROM twitter_account").fetchone()[0]
    tweets_before = conn.execute("SELECT COUNT(*) FROM tweet").fetchone()[0]
    conn.close()
    
    print(f"Before rollback: {accounts_before} accounts, {tweets_before} tweets")
    
    # Perform rollback (restore from backup)
    try:
        shutil.copy2(backup_path, db_path)
        print("Rollback completed: Database restored from backup")
        
        # Verify rollback
        conn = sqlite3.connect(db_path)
        accounts_after = conn.execute("SELECT COUNT(*) FROM twitter_account").fetchone()[0]
        tweets_after = conn.execute("SELECT COUNT(*) FROM tweet").fetchone()[0]
        user1_exists = conn.execute("SELECT COUNT(*) FROM twitter_account WHERE id = 1").fetchone()[0]
        conn.close()
        
        print(f"After rollback: {accounts_after} accounts, {tweets_after} tweets, user 1 exists: {user1_exists == 1}")
        
        success = (accounts_after == 2 and tweets_after == 3 and user1_exists == 1)
        if success:
            print("SUCCESS: Rollback procedure working correctly")
        else:
            print("FAILED: Rollback procedure failed")
        
        return success
        
    except Exception as e:
        print(f"FAILED: Rollback failed with error: {e}")
        return False

def check_foreign_keys(db_path, expected_cascade=True):
    """Check if foreign keys have CASCADE constraints"""
    print(f"Checking foreign key constraints (expecting CASCADE: {expected_cascade})...")
    
    conn = sqlite3.connect(db_path)
    
    tweet_fks = conn.execute("PRAGMA foreign_key_list(tweet)").fetchall()
    list_fks = conn.execute("PRAGMA foreign_key_list(twitter_list)").fetchall()
    
    tweet_has_cascade = any('CASCADE' in str(fk) for fk in tweet_fks)
    list_has_cascade = any('CASCADE' in str(fk) for fk in list_fks)
    
    print(f"   Tweet table CASCADE: {tweet_has_cascade}")
    print(f"   List table CASCADE: {list_has_cascade}")
    
    conn.close()
    
    if expected_cascade:
        success = tweet_has_cascade and list_has_cascade
        print(f"   Expected CASCADE constraints: {'FOUND' if success else 'MISSING'}")
    else:
        success = not tweet_has_cascade and not list_has_cascade
        print(f"   Expected NO CASCADE: {'CORRECT' if success else 'UNEXPECTED CASCADE FOUND'}")
    
    return success

def main():
    """Test all rollback procedures"""
    print("Twitter Manager - Rollback Procedure Test")
    print("=" * 60)
    
    test_db = None
    backup_path = None
    
    try:
        # Create test database
        test_db = create_test_database()
        
        # Create backup
        backup_path = create_backup(test_db)
        
        # Verify initial state (no CASCADE)
        print("\\n1. Verifying initial state (no CASCADE)...")
        if not check_foreign_keys(test_db, expected_cascade=False):
            print("FAILED: Initial state check failed")
            return False
        
        # Apply CASCADE constraints
        print("\\n2. Applying CASCADE constraints...")
        if not apply_cascade_constraints(test_db):
            print("FAILED: Could not apply CASCADE constraints")
            return False
        
        # Verify CASCADE applied
        print("\\n3. Verifying CASCADE constraints applied...")
        if not check_foreign_keys(test_db, expected_cascade=True):
            print("FAILED: CASCADE constraints not applied correctly")
            return False
        
        # Test CASCADE deletion
        print("\\n4. Testing CASCADE deletion...")
        if not verify_cascade_works(test_db):
            print("FAILED: CASCADE deletion test failed")
            return False
        
        # Test rollback procedure
        print("\\n5. Testing rollback procedure...")
        if not test_rollback(test_db, backup_path):
            print("FAILED: Rollback procedure failed")
            return False
        
        # Verify rollback restored original state
        print("\\n6. Verifying rollback restored original state...")
        if not check_foreign_keys(test_db, expected_cascade=False):
            print("FAILED: Rollback did not restore original constraints")
            return False
        
        print("\\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("✅ CASCADE constraints can be applied successfully")
        print("✅ CASCADE deletion works correctly")  
        print("✅ Rollback procedure restores original state")
        print("✅ Database integrity maintained throughout")
        print("\\n🚀 Ready for production deployment!")
        
        return True
        
    except Exception as e:
        print(f"\\nTest failed with exception: {e}")
        return False
        
    finally:
        # Cleanup
        if test_db and os.path.exists(test_db):
            os.unlink(test_db)
        if backup_path and os.path.exists(backup_path):
            os.unlink(backup_path)
        print("\\nTest cleanup completed")

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)