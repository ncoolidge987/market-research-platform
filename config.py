"""
Global configuration settings for the Market Research Platform
"""

import os

class Config:
    """Base configuration for the main application."""
    
    # Base directory of the application
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-development-only')
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    
    # Add more global configuration variables as needed