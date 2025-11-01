# config.py - Advanced configuration with environment variables
import os

class Config:
    """Configuration class for the Telegram bot."""
    
    # Telegram Bot Token
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'your_bot_token_here')
    
    # ImgBB API Key
    IMGBB_API_KEY = os.getenv('IMGBB_API_KEY', 'your_imgbb_api_key_here')
    
    # File size limits (default: 10MB)
    MAX_SIZE_MB = int(os.getenv('MAX_SIZE_MB', 10))
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
    
    # ImgBB API endpoint
    IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
    
    # Webhook configuration
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)  # Set to None for polling
    PORT = int(os.getenv('PORT', 8000))
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your_webhook_secret')
    
    # Bot settings
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'YourBotUsername')
    
    # Validation
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        required = {
            'BOT_TOKEN': cls.BOT_TOKEN,
            'IMGBB_API_KEY': cls.IMGBB_API_KEY
        }
        
        missing = [key for key, value in required.items() if not value or value.startswith('your_')]
        
        if missing:
            raise ValueError(f"Missing or invalid configuration: {', '.join(missing)}")
        
        if cls.MAX_SIZE_MB > 20:
            raise ValueError("MAX_SIZE_MB cannot exceed 20MB due to Telegram limitations")
        
        print("✅ Configuration validated successfully!")
        print(f"🤖 Bot: {cls.BOT_USERNAME}")
        print(f"📁 Max file size: {cls.MAX_SIZE_MB}MB")
        print(f"🌐 Mode: {'Webhook' if cls.WEBHOOK_URL else 'Polling'}")

# Create config instance
config = Config()

# Validate configuration on import
try:
    config.validate()
except ValueError as e:
    print(f"❌ Configuration Error: {e}")
    raise
