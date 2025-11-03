import os
from typing import Set

class Config:
    def __init__(self):
        # Telegram Bot Configuration
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
        self.CHAT_ID = os.getenv("CHAT_ID", "your_chat_id_here")
        
        # RSS Feed Configuration
        self.RSS_FEED_URL = os.getenv("RSS_FEED_URL", "https://example.com/feed")
        
        # Timing Configuration
        self.CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL", 300))  # 5 minutes
        self.DAILY_SUMMARY_HOUR = int(os.getenv("DAILY_SUMMARY_HOUR", 9))  # 9 AM
        
        # File Paths
        self.SENT_LINKS_FILE = "sent_links.json"
        self.LAST_SENT_FILE = "last_sent.txt"
        
        # Flask Configuration
        self.FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
        self.FLASK_PORT = int(os.getenv("FLASK_PORT", 8000))
    
    def validate(self):
        """Validate configuration"""
        if not self.BOT_TOKEN or self.BOT_TOKEN == "your_bot_token_here":
            raise ValueError("BOT_TOKEN is not set")
        if not self.CHAT_ID or self.CHAT_ID == "your_chat_id_here":
            raise ValueError("CHAT_ID is not set")
        if not self.RSS_FEED_URL:
            raise ValueError("RSS_FEED_URL is not set")

config = Config()
