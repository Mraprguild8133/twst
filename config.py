import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API Configuration
    API_ID = int(os.getenv('API_ID', 0))
    API_HASH = os.getenv('API_HASH', '')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    
    # Wasabi Storage Configuration
    WASABI_ACCESS_KEY = os.getenv('WASABI_ACCESS_KEY', '')
    WASABI_SECRET_KEY = os.getenv('WASABI_SECRET_KEY', '')
    WASABI_BUCKET = os.getenv('WASABI_BUCKET', '')
    WASABI_REGION = os.getenv('WASABI_REGION', 'us-east-1')
    WASABI_ENDPOINT = f'https://s3.{WASABI_REGION}.wasabisys.com'
    
    # Bot Configuration
    MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    TEMP_DIR = "temp_files"
    
    # URL Expiration (in seconds)
    URL_EXPIRATION = 3600  # 1 hour

    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required environment variables are set"""
        required_vars = [
            'API_ID', 'API_HASH', 'BOT_TOKEN',
            'WASABI_ACCESS_KEY', 'WASABI_SECRET_KEY', 'WASABI_BUCKET'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True

# Global config instance
config = Config()
