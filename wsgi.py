#!/usr/bin/env python3
"""
WSGI entry point for the Twitter Manager application.
This file is used by Gunicorn to run the Flask application in production.
"""

import sys
import os

# Add the parent directory to the path to avoid conflicts with app/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app from app.py (not the app/ directory)
import app as app_module

# Get the Flask application instance
app = app_module.app

if __name__ == "__main__":
    app.run()