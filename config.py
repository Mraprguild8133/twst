# config.py
import os
from typing import List, Optional

class Config:
    """Configuration class with validation"""
    def __init__(self):
        # Telegram API Configuration
        self.API_ID = int(os.getenv("API_ID", 0))
        self.API_HASH = os.getenv("API_HASH", "")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        
        # Bot Settings
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 4294967296))  # 4GB default
        self.ALLOWED_USER_IDS = [
            int(x.strip()) for x in 
            os.getenv("ALLOWED_USER_IDS", "").split(",") 
            if x.strip()
        ]
        self.SESSION_NAME = os.getenv("SESSION_NAME", "torrent_converter_bot")
        
        # Download Settings
        self.REAL_DEBRID_API_KEY = os.getenv("REAL_DEBRID_API_KEY", "")
        self.PREMIUMIZE_API_KEY = os.getenv("PREMIUMIZE_API_KEY", "")
        self.TORRENT_CLIENT_URL = os.getenv("TORRENT_CLIENT_URL", "")
        self.TORRENT_CLIENT_USERNAME = os.getenv("TORRENT_CLIENT_USERNAME", "")
        self.TORRENT_CLIENT_PASSWORD = os.getenv("TORRENT_CLIENT_PASSWORD", "")
        
        # Rate Limiting
        self.REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "5"))
        
    def validate(self) -> bool:
        """Validate essential configuration"""
        if not all([self.API_ID, self.API_HASH, self.BOT_TOKEN]):
            return False
        return True
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        if not self.ALLOWED_USER_IDS:  # Empty list means all users allowed
            return True
        return user_id in self.ALLOWED_USER_IDS

# Global config instance
config = Config()
