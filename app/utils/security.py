from functools import wraps
from flask import request, jsonify
from cryptography.fernet import Fernet
from app.core.config import Config
import hashlib

# Initialize Fernet encryption
fernet = Fernet(Config.ENCRYPTION_KEY.encode() if isinstance(Config.ENCRYPTION_KEY, str) else Config.ENCRYPTION_KEY)

def check_api_key():
    """Simple API key check"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        api_key = request.args.get('api_key')
    
    if api_key != Config.API_KEY:
        return False
    return True

def require_api_key(f):
    """Decorator to require API key for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_api_key():
            return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def encrypt_token(token):
    """Encrypt a token for storage"""
    try:
        return fernet.encrypt(token.encode()).decode()
    except Exception as e:
        raise Exception(f"Failed to encrypt token: {str(e)}")

def decrypt_token(encrypted_token):
    """Decrypt an encrypted token"""
    try:
        return fernet.decrypt(encrypted_token.encode()).decode()
    except:
        return encrypted_token  # Return as-is if decryption fails

def hash_api_key(api_key):
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()