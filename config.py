import os
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    """Configuration class for URL Shortener Bot"""
    
    # Bot Configuration
    BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
    
    # API Keys for URL Shortening Services
    SHRINKEARN_API = os.environ.get('SHRINKEARN_API', '')
    SHRTFLY_API = os.environ.get('SHRTFLY_API', '')
    GPLINKS_API = os.environ.get('GPLINKS_API', '')
    
    # Webhook Configuration (for Render/Heroku)
    USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'
    WEBHOOK_PORT = int(os.environ.get('PORT', 5000))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
    
    # Bot Appearance
    WELCOME_IMAGE_URL = os.environ.get('WELCOME_IMAGE_URL', 'https://iili.io/Kcbrql9.th.jpg')
    BOT_NAME = os.environ.get('BOT_NAME', 'URL Shortener Bot')
    
    # Supported URL Shortening Services Configuration
    SUPPORTED_SERVICES = {
        'shrinkearn': {
            'name': 'Shrinkearn',
            'api_url': 'https://shrinkearn.com/api',
            'requires_key': True,
            'website': 'https://shrinkearn.com',
            'description': 'Professional URL shortening with analytics'
        },
        'tinyurl': {
            'name': 'TinyURL',
            'api_url': 'http://tinyurl.com/api-create.php',
            'requires_key': False,
            'website': 'https://tinyurl.com',
            'description': 'Simple, reliable, no API key required'
        },
        'shrtfly': {
            'name': 'ShrtFly',
            'api_url': 'https://shrtfly.com/api',
            'requires_key': True,
            'website': 'https://shrtfly.com',
            'description': 'Advanced analytics and customization'
        },
        'gplinks': {
            'name': 'GPLinks',
            'api_url': 'https://gplinks.in/api',
            'requires_key': True,
            'website': 'https://gplinks.in',
            'description': 'Earn money from your shortened links'
        }
    }
    
    # Request Configuration
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 15))
    MAX_URL_LENGTH = int(os.environ.get('MAX_URL_LENGTH', 2048))
    
    # Cache Configuration
    CACHE_EXPIRY = int(os.environ.get('CACHE_EXPIRY', 3600))  # 1 hour in seconds
    
    # Admin Configuration
    ADMIN_IDS = os.environ.get('ADMIN_IDS', '').split(',') if os.environ.get('ADMIN_IDS') else []
    
    # Feature Flags
    ENABLE_ANALYTICS = os.environ.get('ENABLE_ANALYTICS', 'false').lower() == 'true'
    ENABLE_RATE_LIMITING = os.environ.get('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
    
    @classmethod
    def validate_config(cls):
        """Validate essential configuration"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("❌ BOT_TOKEN is required")
        
        # Check if required API keys are present for enabled services
        for service_key, service_info in cls.SUPPORTED_SERVICES.items():
            if service_info['requires_key']:
                api_key = getattr(cls, f"{service_key.upper()}_API", None)
                if not api_key:
                    errors.append(f"❌ {service_info['name']} API key not configured")
        
        return errors
    
    @classmethod
    def get_service_status(cls):
        """Get status of all services"""
        status = {}
        for service_key, service_info in cls.SUPPORTED_SERVICES.items():
            if service_info['requires_key']:
                api_key = getattr(cls, f"{service_key.upper()}_API", None)
                status[service_key] = {
                    'name': service_info['name'],
                    'configured': bool(api_key),
                    'requires_key': service_info['requires_key'],
                    'key_preview': f"{api_key[:8]}..." if api_key and len(api_key) > 8 else ('Set' if api_key else 'Not set')
                }
            else:
                status[service_key] = {
                    'name': service_info['name'],
                    'configured': True,
                    'requires_key': False,
                    'key_preview': 'Not required'
                }
        return status
    
    @classmethod
    def print_config_summary(cls):
        """Print configuration summary"""
        print("🤖 URL Shortener Bot Configuration Summary")
        print("=" * 50)
        
        print(f"📱 Bot Name: {cls.BOT_NAME}")
        print(f"🔑 Bot Token: {'✅ Set' if cls.BOT_TOKEN else '❌ Missing'}")
        print(f"🌐 Webhook Mode: {'Enabled' if cls.USE_WEBHOOK else 'Disabled'}")
        
        if cls.USE_WEBHOOK:
            print(f"📡 Webhook URL: {cls.WEBHOOK_URL if cls.WEBHOOK_URL else 'Using platform default'}")
            print(f"🔌 Webhook Port: {cls.WEBHOOK_PORT}")
        
        print(f"🖼️ Welcome Image: {'✅ Accessible' if cls.WELCOME_IMAGE_URL else '❌ Not set'}")
        
        print("\n📊 Supported Services Status:")
        for service_key, status in cls.get_service_status().items():
            icon = "✅" if status['configured'] else "❌"
            print(f"   {icon} {status['name']}: {status['key_preview']}")
        
        print(f"\n⚙️ Additional Features:")
        print(f"   📊 Analytics: {'Enabled' if cls.ENABLE_ANALYTICS else 'Disabled'}")
        print(f"   🚦 Rate Limiting: {'Enabled' if cls.ENABLE_RATE_LIMITING else 'Disabled'}")
        print(f"   👥 Admin Users: {len(cls.ADMIN_IDS)}")
        
        # Validate configuration
        errors = cls.validate_config()
        if errors:
            print(f"\n❌ Configuration Errors:")
            for error in errors:
                print(f"   {error}")
        else:
            print(f"\n✅ Configuration is valid!")
        
        print("=" * 50)

# Create config instance
config = Config()

if __name__ == '__main__':
    # Print configuration summary when run directly
    config.print_config_summary()        }
    }

config = Config()
