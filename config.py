# config.py
import os
from typing import List

class Config:
    """Configuration class for the bot."""
    
    def __init__(self):
        # Telegram API Configuration
        self.API_ID = int(os.environ["API_ID"])
        self.API_HASH = os.environ["API_HASH"]
        self.BOT_TOKEN = os.environ["BOT_TOKEN"]
        
        # Admin IDs
        admin_ids = os.environ.get("ADMIN_IDS", "")
        self.ADMIN_IDS = [int(i.strip()) for i in admin_ids.split(',') if i.strip().isdigit()]
        
        # Log Channel
        self.LOG_CHANNEL_ID = int(os.environ["LOG_CHANNEL_ID"])
        
        # Wasabi Configuration
        self.WASABI_ACCESS_KEY = os.environ["WASABI_ACCESS_KEY"]
        self.WASABI_SECRET_KEY = os.environ["WASABI_SECRET_KEY"]
        self.WASABI_BUCKET = os.environ["WASABI_BUCKET"]
        self.WASABI_REGION = os.environ["WASABI_REGION"]
        
        # Bot Settings
        self.MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
        self.DOWNLOAD_PATH = "./downloads"
        self.LINK_EXPIRY = 3600 * 24 * 7  # 7 days

    def validate(self):
        """Validate required configuration."""
        required_vars = [
            "API_ID", "API_HASH", "BOT_TOKEN", "LOG_CHANNEL_ID",
            "WASABI_ACCESS_KEY", "WASABI_SECRET_KEY", "WASABI_BUCKET", "WASABI_REGION"
        ]
        
        for var in required_vars:
            if not getattr(self, var):
                raise ValueError(f"Required environment variable for {var} is missing or empty")

# Create global config instance
try:
    config = Config()
    config.validate()
except (KeyError, ValueError) as e:
    print(f"Configuration error: {e}")
    exit(1)
