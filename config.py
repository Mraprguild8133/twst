import os
from typing import List, Set

class Config:
    # Bot API credentials
    API_ID = int(os.getenv("API_ID", 12345678))
    API_HASH = os.getenv("API_HASH", "your_api_hash_here")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
    
    # Storage
    STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID", -1001234567890))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 2000))  # MB
    
    # Admin management
    ADMIN_IDS: Set[int] = set()
    BOT_USERNAME = None
    
    # Web interface
    WEB_PORT = int(os.getenv("WEB_PORT", 8000))
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    
    def __init__(self):
        self._load_admin_ids()
    
    def _load_admin_ids(self):
        """Load admin IDs from environment variable"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if admin_ids_str:
            self.ADMIN_IDS = set(map(int, admin_ids_str.split(',')))
        
        # Add owner from environment
        owner_id = os.getenv("OWNER_ID")
        if owner_id:
            self.ADMIN_IDS.add(int(owner_id))
    
    def add_admin(self, user_id: int):
        """Add a new admin user"""
        self.ADMIN_IDS.add(user_id)
        self._save_admin_ids()
    
    def remove_admin(self, user_id: int):
        """Remove an admin user"""
        self.ADMIN_IDS.discard(user_id)
        self._save_admin_ids()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.ADMIN_IDS
    
    def _save_admin_ids(self):
        """Save admin IDs to environment (in production, use database)"""
        # In a real application, save to database
        print(f"Admin IDs updated: {self.ADMIN_IDS}")

config = Config()
