#!/usr/bin/env python3
"""
WSGI entry point for the Twitter Manager application.
This file is used by Gunicorn to run the Flask application in production.
"""

from app import create_app

# Create the Flask application using the factory pattern
app = create_app()

if __name__ == "__main__":
    app.run()