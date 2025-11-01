# config.py
import os

class Config:
    """Configuration class for the Telegram bot."""
    
    # Required API keys
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'your_bot_token_here')
    IMGBB_API_KEY = os.getenv('IMGBB_API_KEY', 'your_imgbb_api_key_here')
    
    # File size limits
    MAX_SIZE_MB = int(os.getenv('MAX_SIZE_MB', 32))
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
    
    # ImgBB API endpoint
    IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
    
    # Webhook configuration
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)  # Set to None for polling mode
    PORT = int(os.getenv('PORT', 8000))
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your_webhook_secret_here')
    
    # Server settings
    LISTEN_ADDRESS = os.getenv('LISTEN_ADDRESS', '0.0.0.0')
    
    def validate(self):
        """Validate configuration settings."""
        if not self.BOT_TOKEN or self.BOT_TOKEN == 'your_bot_token_here':
            raise ValueError("BOT_TOKEN is not set properly")
        
        if not self.IMGBB_API_KEY or self.IMGBB_API_KEY == 'your_imgbb_api_key_here':
            raise ValueError("IMGBB_API_KEY is not set properly")
        
        if self.MAX_SIZE_MB > 20:
            raise ValueError("MAX_SIZE_MB cannot exceed 20MB due to Telegram limitations")
        
        if self.WEBHOOK_URL and not self.WEBHOOK_URL.startswith('https://'):
            print("⚠️  Warning: WEBHOOK_URL should use HTTPS for production")
        
        return True

# Create config instance
config = Config()

# Validate configuration
try:
    config.validate()
    print("✅ Configuration validated successfully!")
    print(f"📁 Max file size: {config.MAX_SIZE_MB}MB")
    print(f"🌐 Mode: {'Webhook' if config.WEBHOOK_URL else 'Polling'}")
    if config.WEBHOOK_URL:
        print(f"🔗 Webhook URL: {config.WEBHOOK_URL}")
        print(f"🔄 Port: {config.PORT}")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    raise
