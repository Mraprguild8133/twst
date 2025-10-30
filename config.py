import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Configuration
    API_ID: str = os.getenv('API_ID')
    API_HASH: str = os.getenv('API_HASH')
    BOT_TOKEN: str = os.getenv('BOT_TOKEN')
    
    # Wasabi Configuration
    WASABI_ACCESS_KEY: str = os.getenv('WASABI_ACCESS_KEY')
    WASABI_SECRET_KEY: str = os.getenv('WASABI_SECRET_KEY')
    WASABI_BUCKET: str = os.getenv('WASABI_BUCKET')
    WASABI_REGION: str = os.getenv('WASABI_REGION', 'us-east-1')
    
    # Bot Configuration
    MAX_FILE_SIZE: int = 4 * 1024 * 1024 * 1024  # 4GB
    VERIFICATION_URL: str = "https://gplinks.in"
    
    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set"""
        required_vars = {
            'API_ID': cls.API_ID,
            'API_HASH': cls.API_HASH,
            'BOT_TOKEN': cls.BOT_TOKEN,
            'WASABI_ACCESS_KEY': cls.WASABI_ACCESS_KEY,
            'WASABI_SECRET_KEY': cls.WASABI_SECRET_KEY,
            'WASABI_BUCKET': cls.WASABI_BUCKET,
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Global config instance
config = Config()
