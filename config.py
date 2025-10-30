import os
from typing import List

class Config:
    """Configuration class for the Telegram File Store Bot"""
    
    def __init__(self):
        # Required environment variables
        self.API_ID = int(os.environ['API_ID'])
        self.API_HASH = os.environ['API_HASH']
        self.BOT_TOKEN = os.environ['BOT_TOKEN']
        
        # Admin IDs - comma separated string of user IDs
        admin_ids_str = os.environ.get('ADMIN_IDS', '')
        self.ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(',')] if admin_ids_str else []
        
        # Storage chat ID (default to first admin if not specified)
        self.STORAGE_CHAT_ID = int(os.environ.get('STORAGE_CHAT_ID', self.ADMIN_IDS[0] if self.ADMIN_IDS else None))
        
        # Optional settings with defaults
        self.MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 2000))  # in MB
        self.ALLOWED_FILE_TYPES = os.environ.get('ALLOWED_FILE_TYPES', 'document,video,audio').split(',')
        self.BOT_USERNAME = None  # Will be set dynamically
        
    def validate(self):
        """Validate required configuration"""
        if not self.ADMIN_IDS:
            raise ValueError("At least one ADMIN_ID must be specified")
        if not self.STORAGE_CHAT_ID:
            raise ValueError("STORAGE_CHAT_ID must be specified")
        return self

# Create global config instance
config = Config().validate()
