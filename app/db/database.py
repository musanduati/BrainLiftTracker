import sqlite3
import hashlib
from app.core.config import Config

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    try:
        conn = get_db()
        
        # Enable WAL mode once for better concurrent access
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')  # 5 seconds
        
        # Create api_key table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_key (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create twitter_account table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS twitter_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                access_token_secret TEXT,
                refresh_token TEXT,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                token_expires_at DATETIME,
                last_token_refresh DATETIME,
                refresh_failure_count INTEGER DEFAULT 0,
                account_type TEXT DEFAULT 'managed',
                display_name TEXT,
                profile_picture TEXT,
                workflowy_url TEXT
            )
        ''')
        
        # Create tweet table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tweet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_account_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                twitter_id TEXT,
                thread_id TEXT,
                reply_to_tweet_id TEXT,
                thread_position INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                posted_at DATETIME,
                FOREIGN KEY (twitter_account_id) REFERENCES twitter_account (id)
            )
        ''')
        
        # Create oauth_state table if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS oauth_state (
                state TEXT PRIMARY KEY,
                code_verifier TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
        ''')
        
        # Create twitter_list table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS twitter_list (
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
                FOREIGN KEY (owner_account_id) REFERENCES twitter_account(id)
            )
        ''')
        
        # Create list_membership table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS list_membership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES twitter_list(id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES twitter_account(id) ON DELETE CASCADE,
                UNIQUE(list_id, account_id)
            )
        ''')
        
        # Create follower table for tracking approved followers
        conn.execute('''
            CREATE TABLE IF NOT EXISTS follower (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                follower_username TEXT NOT NULL,
                follower_id TEXT,
                follower_name TEXT,
                approved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (account_id) REFERENCES twitter_account(id) ON DELETE CASCADE,
                UNIQUE(account_id, follower_username)
            )
        ''')
        
        # Create index for faster lookups
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_follower_account 
            ON follower(account_id)
        ''')
        
        # Create OAuth 1.0a request tokens table (separate from OAuth 2.0)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS oauth1_request_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT UNIQUE NOT NULL,
                account_id INTEGER NOT NULL,
                oauth_token TEXT NOT NULL,
                oauth_token_secret TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (account_id) REFERENCES twitter_account(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for OAuth 1.0a table
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_oauth1_tokens_state 
            ON oauth1_request_tokens(state)
        ''')
        
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_oauth1_tokens_account 
            ON oauth1_request_tokens(account_id)
        ''')
        
        # Migrate existing tables - add columns if they don't exist
        _migrate_database(conn)
        
        # Insert API key from environment if not exists
        if Config.API_KEY:
            key_hash = hashlib.sha256(Config.API_KEY.encode()).hexdigest()
            try:
                conn.execute('INSERT INTO api_key (key_hash) VALUES (?)', (key_hash,))
                print("API key added to database")
            except sqlite3.IntegrityError:
                pass  # Key already exists
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        # Error initializing database
        raise e  # Re-raise to prevent app from starting with broken DB

def _migrate_database(conn):
    """Apply database migrations for existing tables"""
    migrations = [
        ('twitter_account', 'refresh_token TEXT'),
        ('twitter_account', 'updated_at DATETIME'),
        ('twitter_account', 'token_expires_at DATETIME'),
        ('twitter_account', 'last_token_refresh DATETIME'),
        ('twitter_account', 'refresh_failure_count INTEGER DEFAULT 0'),
        ('twitter_account', "account_type TEXT DEFAULT 'managed'"),
        ('twitter_account', 'display_name TEXT'),
        ('twitter_account', 'profile_picture TEXT'),
        ('twitter_account', 'workflowy_url TEXT'),
        ('tweet', 'thread_id TEXT'),
        ('tweet', 'reply_to_tweet_id TEXT'),
        ('tweet', 'thread_position INTEGER'),
        ('twitter_list', 'source VARCHAR(20) DEFAULT "created"'),
        ('twitter_list', 'external_owner_username VARCHAR(255)'),
        ('twitter_list', 'last_synced_at DATETIME'),
        ('twitter_list', 'is_managed BOOLEAN DEFAULT 1'),
        ('tweet', 'dok_type VARCHAR(10)'),
        ('tweet', 'change_type VARCHAR(10)'),
        # OAuth 1.0a tokens for profile updates (separate from OAuth 2.0)
        ('twitter_account', 'oauth1_access_token TEXT'),
        ('twitter_account', 'oauth1_access_token_secret TEXT'),
        ('twitter_account', 'oauth1_authorized_at DATETIME'),
    ]
    
    for table, column_def in migrations:
        try:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {column_def}')
            print(f"Added column {column_def.split()[0]} to {table} table")
        except:
            pass  # Column already exists