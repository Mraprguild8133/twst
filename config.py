import os
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
    
    # API Keys for URL shortening services
    API_KEYS = {
        'gplinks': os.getenv("GPLINKS_API_KEY", "YOUR_GPLINKS_API_KEY_HERE"),
        'shrinkearn': os.getenv("SHRINKEARN_API_KEY", "YOUR_SHRINKEARN_API_KEY_HERE"),
        'shrtfly': os.getenv("SHRTFLY_API_KEY", "YOUR_SHRTFLY_API_KEY_HERE"),
        'fclc': os.getenv("FCLC_API_KEY", "YOUR_FCLC_API_KEY_HERE"),
    }
    
    # API Endpoints
    SERVICE_ENDPOINTS = {
        'gplinks': 'https://gplinks.in/api',
        'shrinkearn': 'https://shrinkearn.com/api',
        'shrtfly': 'https://shrtfly.com/api',
        'fclc': 'https://fc.lc/api',
    }
    
    # Placeholder keys to check against
    PLACEHOLDER_KEYS = [
        "YOUR_GPLINKS_API_KEY_HERE",
        "YOUR_SHRINKEARN_API_KEY_HERE", 
        "YOUR_SHRTFLY_API_KEY_HERE",
        "YOUR_FCLC_API_KEY_HERE"
    ]

# Create config instance
config = Config()
