import os
from typing import Optional

class Config:
    """Configuration class for the RSS Bot"""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # RSS Feed Configuration
    RSS_FEED_URL: str = os.getenv("RSS_FEED_URL", "")
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))
    
    # File Storage
    LAST_SENT_FILE: str = os.getenv("LAST_SENT_FILE", "last_sent_link.txt")
    
    # Validation
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is set"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        if not cls.CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        
        if not cls.RSS_FEED_URL:
            raise ValueError("RSS_FEED_URL environment variable is required")
        
        return True

# Create config instance
config = Config()
