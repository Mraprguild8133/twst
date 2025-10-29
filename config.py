import os
import json
from typing import List, Union

class Config:
    """Configuration class for Wasabi Upload Bot"""
    
    def __init__(self):
        # Telegram API Configuration
        self.API_ID = self._get_env_int("API_ID")
        self.API_HASH = self._get_env("API_HASH")
        self.BOT_TOKEN = self._get_env("BOT_TOKEN")
        
        # Admin Configuration
        self.ADMIN_IDS = self._get_admin_ids()
        
        # Wasabi S3 Configuration
        self.WASABI_ACCESS_KEY = self._get_env("WASABI_ACCESS_KEY")
        self.WASABI_SECRET_KEY = self._get_env("WASABI_SECRET_KEY")
        self.WASABI_BUCKET = self._get_env("WASABI_BUCKET", "wasabi-upload-bot")
        self.WASABI_REGION = self._get_env("WASABI_REGION", "us-east-1")
        
        # File Upload Configuration
        self.MAX_FILE_SIZE = self._get_env_int("MAX_FILE_SIZE", 4 * 1024 * 1024 * 1024)  # 4GB default
        self.CHUNK_SIZE = self._get_env_int("CHUNK_SIZE", 100 * 1024 * 1024)  # 100MB chunks
        
        # Payment Configuration (with defaults)
        self.SUBSCRIPTION_PRICE = self._get_env_int("SUBSCRIPTION_PRICE", 100)
        self.SUBSCRIPTION_DAYS = self._get_env_int("SUBSCRIPTION_DAYS", 30)
        
        # URL Shortener Configuration
        self.GPLINKS_API_KEY = self._get_env("GPLINKS_API_KEY", "")
        self.AUTO_SHORTEN = self._get_env_bool("AUTO_SHORTEN", True)
        
        # Player Configuration
        self.RENDER_URL = self._get_env("RENDER_URL", "http://localhost:8000")
        
        # Validate required configurations
        self._validate_config()
    
    def _get_env(self, key: str, default: str = None) -> str:
        """Get environment variable with optional default"""
        value = os.getenv(key, default)
        if value is None:
            raise ValueError(f"❌ Required environment variable {key} is not set")
        return value
    
    def _get_env_int(self, key: str, default: int = None) -> int:
        """Get integer environment variable"""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ValueError(f"❌ Required environment variable {key} is not set")
            return default
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"❌ Environment variable {key} must be an integer")
    
    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'y')
    
    def _get_admin_ids(self) -> List[int]:
        """Parse admin IDs from environment variable"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if not admin_ids_str:
            raise ValueError("❌ ADMIN_IDS environment variable is required")
        
        try:
            # Support both comma-separated and JSON array format
            if admin_ids_str.startswith('['):
                admin_ids = json.loads(admin_ids_str)
            else:
                admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')]
            
            return [int(admin_id) for admin_id in admin_ids]
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"❌ Invalid ADMIN_IDS format: {e}")
    
    def _validate_config(self):
        """Validate configuration values"""
        # Validate file sizes
        if self.MAX_FILE_SIZE <= 0:
            raise ValueError("MAX_FILE_SIZE must be positive")
        
        if self.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE must be positive")
        
        if self.CHUNK_SIZE > self.MAX_FILE_SIZE:
            raise ValueError("CHUNK_SIZE cannot be larger than MAX_FILE_SIZE")
        
        # Validate subscription settings
        if self.SUBSCRIPTION_PRICE <= 0:
            raise ValueError("SUBSCRIPTION_PRICE must be positive")
        
        if self.SUBSCRIPTION_DAYS <= 0:
            raise ValueError("SUBSCRIPTION_DAYS must be positive")
        
        # Validate Wasabi region
        valid_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-central-1',
            'eu-central-1', 'eu-west-1', 'eu-west-2', 'ap-northeast-1',
            'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2'
        ]
        if self.WASABI_REGION not in valid_regions:
            raise ValueError(f"Invalid WASABI_REGION. Must be one of: {', '.join(valid_regions)}")
        
        # Log configuration summary (without sensitive data)
        self._log_config_summary()
    
    def _log_config_summary(self):
        """Log configuration summary (safe version without secrets)"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("🔧 Configuration Summary:")
        logger.info(f"   • API_ID: {self.API_ID}")
        logger.info(f"   • API_HASH: {self.API_HASH[:10]}...")
        logger.info(f"   • BOT_TOKEN: {self.BOT_TOKEN[:10]}...")
        logger.info(f"   • ADMIN_IDS: {self.ADMIN_IDS}")
        logger.info(f"   • WASABI_BUCKET: {self.WASABI_BUCKET}")
        logger.info(f"   • WASABI_REGION: {self.WASABI_REGION}")
        logger.info(f"   • MAX_FILE_SIZE: {self._human_bytes(self.MAX_FILE_SIZE)}")
        logger.info(f"   • CHUNK_SIZE: {self._human_bytes(self.CHUNK_SIZE)}")
        logger.info(f"   • SUBSCRIPTION_PRICE: ₹{self.SUBSCRIPTION_PRICE}")
        logger.info(f"   • SUBSCRIPTION_DAYS: {self.SUBSCRIPTION_DAYS} days")
        logger.info(f"   • AUTO_SHORTEN: {self.AUTO_SHORTEN}")
        logger.info(f"   • RENDER_URL: {self.RENDER_URL}")
    
    def _human_bytes(self, size: int) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

# Global configuration instance
config = Config()
