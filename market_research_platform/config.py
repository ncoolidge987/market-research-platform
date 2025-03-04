"""
Configuration settings for the Market Research Platform
"""

import os

class Config:
    """Base configuration."""
    # Base directory of the application
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    # SQLite database paths for each data source
    ESR_DB_PATH = os.path.join(BASEDIR, "modules/weekly_export_sales/data/esr_data.db")
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-development-only')
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    
    # Add more configuration variables as needed