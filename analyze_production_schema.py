#!/usr/bin/env python3
"""
Analyze Production Database Schema

This script analyzes the actual production database schema to understand
the column differences that caused the deployment failure.
"""

import sqlite3
import sys
import os

def analyze_table_schema(db_path, table_name):
    """Analyze the schema of a specific table"""
    try:
        conn = sqlite3.connect(db_path)
        
        # Get table info
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        
        print(f"\n📋 {table_name.upper()} TABLE SCHEMA:")
        print(f"Total columns: {len(columns)}")
        print("Columns:")
        for col in columns:
            cid, name, type_name, notnull, default, pk = col
            nullable = "NOT NULL" if notnull else "NULL"
            pk_info = " (PRIMARY KEY)" if pk else ""
            default_info = f" DEFAULT {default}" if default else ""
            print(f"  {cid+1:2}. {name:<20} {type_name:<10} {nullable:<8} {default_info}{pk_info}")
        
        # Get foreign keys
        foreign_keys = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
        if foreign_keys:
            print(f"\nForeign Keys:")
            for fk in foreign_keys:
                id_fk, seq, table, from_col, to_col, on_update, on_delete, match = fk
                cascade_info = f" ON DELETE {on_delete}" if on_delete else ""
                print(f"  {from_col} -> {table}.{to_col}{cascade_info}")
        else:
            print(f"\nNo foreign key constraints")
        
        # Get a sample record to see the actual data structure
        sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 1").fetchone()
        if sample:
            print(f"\nSample Record ({len(sample)} values):")
            for i, (col_info, value) in enumerate(zip(columns, sample)):
                col_name = col_info[1]
                print(f"  {col_name}: {value}")
        
        conn.close()
        return columns
        
    except Exception as e:
        print(f"Error analyzing {table_name}: {e}")
        return None

def compare_with_expected_schema():
    """Compare with what the deployment script expected"""
    print("\n🔄 EXPECTED vs ACTUAL SCHEMA COMPARISON:")
    print("\nExpected tweet table schema (from deployment script):")
    expected_tweet_columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "twitter_account_id INTEGER NOT NULL", 
        "content TEXT NOT NULL",
        "status TEXT DEFAULT 'pending'",
        "thread_id TEXT",
        "thread_position INTEGER", 
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
    ]
    
    for i, col in enumerate(expected_tweet_columns, 1):
        print(f"  {i:2}. {col}")
    
    print(f"\nExpected columns: {len(expected_tweet_columns)}")
    print("Actual columns: Will be shown above")

def generate_correct_migration_sql(db_path):
    """Generate the correct migration SQL based on actual schema"""
    print("\n🔧 GENERATING CORRECT MIGRATION SQL:")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get the actual CREATE TABLE statement
        schema_sql = conn.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='tweet'
        """).fetchone()
        
        if schema_sql:
            original_sql = schema_sql[0]
            print(f"\nOriginal tweet table SQL:")
            print(original_sql)
            
            # Generate the corrected SQL with CASCADE
            corrected_sql = original_sql.replace(
                "REFERENCES twitter_account (id)",
                "REFERENCES twitter_account (id) ON DELETE CASCADE"
            ).replace(
                "REFERENCES twitter_account(id)",  # Handle both formats
                "REFERENCES twitter_account(id) ON DELETE CASCADE"
            )
            
            print(f"\nCorrected tweet table SQL with CASCADE:")
            print(corrected_sql)
        
        # Do the same for twitter_list
        list_schema_sql = conn.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='twitter_list'
        """).fetchone()
        
        if list_schema_sql:
            original_list_sql = list_schema_sql[0]
            print(f"\nOriginal twitter_list table SQL:")
            print(original_list_sql)
            
            corrected_list_sql = original_list_sql.replace(
                "REFERENCES twitter_account(id)",
                "REFERENCES twitter_account(id) ON DELETE CASCADE"
            ).replace(
                "REFERENCES twitter_account (id)",
                "REFERENCES twitter_account (id) ON DELETE CASCADE"
            )
            
            print(f"\nCorrected twitter_list table SQL with CASCADE:")
            print(corrected_list_sql)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating migration SQL: {e}")

def main():
    """Analyze production database schema"""
    print("Production Database Schema Analysis")
    print("=" * 60)
    
    # Use the production database path
    db_path = "/home/ubuntu/twitter-manager/instance/twitter_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print("Please run this script on the production server")
        return False
    
    print(f"Analyzing database: {db_path}")
    
    # Analyze tweet table (the one that failed)
    tweet_columns = analyze_table_schema(db_path, "tweet")
    if not tweet_columns:
        return False
    
    # Analyze twitter_list table
    list_columns = analyze_table_schema(db_path, "twitter_list")
    
    # Analyze twitter_account table for reference
    account_columns = analyze_table_schema(db_path, "twitter_account")
    
    # Compare with expected schema
    compare_with_expected_schema()
    
    # Generate correct migration SQL
    generate_correct_migration_sql(db_path)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print("Use the corrected SQL above to fix the deployment script")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)