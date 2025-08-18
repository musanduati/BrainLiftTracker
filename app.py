"""
Twitter Manager API - Modular Architecture
This file serves as the entry point for the modularized application.
"""

import os
from app import create_app
from app.core.config import Config

# Create the Flask application using the factory pattern
app = create_app()

if __name__ == '__main__':
    print(f"Database path: {Config.DB_PATH}")
    print(f"Database exists: {os.path.exists(Config.DB_PATH)}")
    print(f"Twitter Callback URL: {Config.TWITTER_CALLBACK_URL}")
    
    # Run the app
    print("\n>>> Starting Twitter Manager API (Modular Architecture)")
    print(">>> API endpoints available at: http://localhost:5555/api/v1/")
    print(">>> Use API key from .env file in headers: X-API-Key: <your-api-key>")
    if Config.API_KEY == "test-api-key-replace-in-production":
        print(">>> WARNING: Using test API key. Set API_KEY in .env for production.")
    print("\nAvailable endpoints (migrated to modular architecture):")
    print("  GET  /api/v1/health (no auth)")
    print("  GET  /api/v1/test")
    print("  GET  /api/v1/auth/twitter - Start OAuth flow")
    print("  GET/POST /api/v1/auth/callback - OAuth callback")
    print("  GET  /api/v1/accounts - Get all accounts")
    print("  GET  /api/v1/accounts/<id> - Get account details")
    print("  POST /api/v1/accounts/<id>/refresh-token - Refresh token")
    print("  GET  /api/v1/accounts/token-health - Check token health")
    print("\nNote: All endpoints have been migrated to the modular architecture.")
    
    app.run(host='0.0.0.0', port=5555, debug=True)