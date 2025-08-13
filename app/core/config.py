import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Load environment variables
load_dotenv()

class Config:
    # Database configuration
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'instance', 'twitter_manager.db')
    
    # API configuration
    API_KEY = os.environ.get('API_KEY')
    if not API_KEY:
        print("WARNING: No API_KEY found in environment. Please set it in .env file.")
        API_KEY = "test-api-key-replace-in-production"
    
    # Encryption configuration
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    if not ENCRYPTION_KEY:
        print("WARNING: No ENCRYPTION_KEY found in environment. Please set it in .env file.")
        ENCRYPTION_KEY = Fernet.generate_key().decode()
    
    # Twitter API configuration
    TWITTER_CLIENT_ID = os.environ.get('TWITTER_CLIENT_ID')
    TWITTER_CLIENT_SECRET = os.environ.get('TWITTER_CLIENT_SECRET')
    TWITTER_CALLBACK_URL = os.environ.get('TWITTER_CALLBACK_URL', 'http://localhost:5555/auth/callback')
    
    if not TWITTER_CLIENT_ID or not TWITTER_CLIENT_SECRET:
        print("WARNING: Twitter API credentials not found in environment.")
        print("Please set TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET in .env file.")
    
    if 'localhost' in TWITTER_CALLBACK_URL and os.environ.get('FLASK_ENV') == 'production':
        print("WARNING: Using localhost callback URL in production environment!")
    
    # Mock mode configuration
    MOCK_TWITTER_POSTING = False
    
    # Flask configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # CORS configuration
    CORS_ORIGINS = [
        "http://localhost:5173", 
        "http://localhost:5174", 
        "http://localhost:5175",
        "http://localhost:3000",
        "http://98.86.153.32",
        "*"
    ]
    
    # Rate limiting configuration
    RATE_LIMIT_TWEETS_PER_15MIN = 180  # Leave buffer of 20 tweets from Twitter's 200 limit
    RATE_LIMIT_WINDOW = 900  # 15 minutes in seconds

# Ensure instance directory exists
os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)