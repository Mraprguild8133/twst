import os
from typing import Optional

class Config:
    """Configuration class for the Telegram bot"""
    
    def __init__(self):
        # Telegram Bot Token
        self.BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
        
        # ImgBB API Key
        self.IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "YOUR_IMGBB_API_KEY_HERE")
        
        # Upload settings
        self.MAX_SIZE_MB = 32
        self.MAX_SIZE_BYTES = self.MAX_SIZE_MB * 1024 * 1024
        self.IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
        
        # Validation
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        missing_vars = []
        
        if self.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not self.BOT_TOKEN:
            missing_vars.append("TELEGRAM_BOT_TOKEN")
        
        if self.IMGBB_API_KEY == "YOUR_IMGBB_API_KEY_HERE" or not self.IMGBB_API_KEY:
            missing_vars.append("IMGBB_API_KEY")
        
        if missing_vars:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_vars)}\n"
                "Please set them as environment variables or update the defaults."
            )

# Create global config instance
config = Config()
