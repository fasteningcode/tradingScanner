#!/usr/bin/env python3
"""
Flask Dashboard Application Entry Point

This script initializes and runs the Flask application.
It should be used to start the development server.

Usage:
    python run.py
    or
    flask run
"""

import os
from app import create_app

# Get configuration from environment variable, default to 'development'
config_name = os.environ.get('FLASK_CONFIG', 'development')

# Create the Flask application instance
app = create_app(config_name)


if __name__ == '__main__':
    # Run the application
    # Debug mode is controlled by the configuration
    app.run(
        host='0.0.0.0',  # Make the server publicly available
        port=5002,       # Default Flask port
        debug=app.config.get('DEBUG', False)
    )
