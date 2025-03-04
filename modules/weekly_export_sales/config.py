"""
Configuration settings specific to the Weekly Export Sales module
"""

import os

class WeeklyExportConfig:
    """Configuration for the Weekly Export Sales module."""
    
    # Base directory of the module
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    # SQLite database path for this module
    DB_PATH = os.path.join(BASEDIR, "data/esr_data.db")
    
    # Module-specific configuration
    DATA_LOG_PATH = os.path.join(BASEDIR, "data/data_collector.log")
    
    # API settings
    API_KEYS = [
        "sXXbup7bXhySZZJBQv5VmmugtL3iW1UoRyjfeHJX",
        "O3NXAWRBr9DTb9EzpgzXcfB0FDhUWnyWSMZaT21u",
        "7eZV4w04Gpwd44zqOKoB92Is9nLwNdtTqqThNqPq",
        "P5cCtban45muGHzXVI9dgrdpnyCuQ1ogyJioOlgo",
        "H6UpwAmkElhx1Vjv3N3f0aBcBGND5KekrBTEXoFP"
    ]
    
    # General settings
    RATE_LIMIT_THRESHOLD = 50
    RETRY_DELAY = 5
    
    # Make sure data directory exists
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist"""
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.DATA_LOG_PATH), exist_ok=True)