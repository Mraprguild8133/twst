import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""
    
    # Telegram API Configuration
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # Wasabi S3 Configuration
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY", "")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY", "")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET", "")
    WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
    
    # Payment Configuration
    MERCHANT_UPI_ID = os.getenv("MERCHANT_UPI_ID", "")
    MERCHANT_NAME = os.getenv("MERCHANT_NAME", "Cloud Storage Pro")
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "123456789"))
    
    # Server Configuration
    RENDER_URL = os.getenv("RENDER_URL", "http://localhost:8000")
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "8000"))
    
    # File Upload Limits (in bytes)
    MAX_FILE_SIZE_FREE = 2 * 1024 * 1024 * 1024  # 2GB for free users
    MAX_FILE_SIZE_PREMIUM = 10 * 1024 * 1024 * 1024  # 10GB for premium users
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "5"))
    RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # seconds
    
    # Database Configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", "premium_users.db")
    
    # Presigned URL Expiry (in seconds)
    PRESIGNED_URL_EXPIRY = 24 * 60 * 60  # 24 hours
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Bot Settings
    BOT_NAME = os.getenv("BOT_NAME", "Wasabi Storage Bot")
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Sathishkumar33")
    SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "mraprguild@gmail.com")
    
    # Owner Information
    OWNER_NAME = os.getenv("OWNER_NAME", "Mraprguild")
    OWNER_USERNAME = os.getenv("OWNER_USERNAME", "@Sathishkumar33")
    
    # Premium Plans Configuration
    PREMIUM_PLANS = {
        "basic": {
            "name": "Basic Plan",
            "price": 299,  # ₹299
            "storage_gb": 50,
            "max_file_size_gb": 4,
            "duration_days": 30,
            "features": [
                "50GB Storage", 
                "4GB File Size", 
                "Priority Support",
                "No Ads"
            ]
        },
        "pro": {
            "name": "Pro Plan", 
            "price": 799,  # ₹799
            "storage_gb": 200,
            "max_file_size_gb": 10,
            "duration_days": 30,
            "features": [
                "200GB Storage", 
                "10GB File Size", 
                "24/7 Priority Support",
                "No Ads",
                "Faster Processing"
            ]
        },
        "annual_pro": {
            "name": "Annual Pro",
            "price": 7999,  # ₹7,999
            "storage_gb": 200,
            "max_file_size_gb": 10,
            "duration_days": 365,
            "features": [
                "200GB Storage", 
                "10GB File Size", 
                "24/7 Priority Support",
                "No Ads", 
                "Faster Processing",
                "2 Months Free"
            ]
        }
    }
    
    # Media Extensions Configuration
    MEDIA_EXTENSIONS = {
        'video': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.flv', '.wmv'],
        'audio': ['.mp3', '.m4a', '.ogg', '.wav', '.flac', '.aac', '.wma'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg']
    }
    
    # Wasabi Endpoint Configuration
    @property
    def wasabi_endpoint_url(self):
        return f'https://s3.{self.WASABI_REGION}.wasabisys.com'
    
    @property
    def wasabi_alternative_endpoint(self):
        return f'https://{self.WASABI_BUCKET}.s3.{self.WASABI_REGION}.wasabisys.com'
    
    def validate_config(self):
        """Validate all required configuration variables"""
        required_vars = [
            ("API_ID", self.API_ID),
            ("API_HASH", self.API_HASH),
            ("BOT_TOKEN", self.BOT_TOKEN),
            ("WASABI_ACCESS_KEY", self.WASABI_ACCESS_KEY),
            ("WASABI_SECRET_KEY", self.WASABI_SECRET_KEY),
            ("WASABI_BUCKET", self.WASABI_BUCKET),
            ("MERCHANT_UPI_ID", self.MERCHANT_UPI_ID)
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Validate API_ID is integer
        if not isinstance(self.API_ID, int) or self.API_ID == 0:
            raise ValueError("API_ID must be a valid integer")
        
        # Validate ADMIN_USER_ID is integer
        if not isinstance(self.ADMIN_USER_ID, int) or self.ADMIN_USER_ID == 0:
            raise ValueError("ADMIN_USER_ID must be a valid integer")
        
        # Validate UPI ID format
        if self.MERCHANT_UPI_ID and '@' not in self.MERCHANT_UPI_ID:
            raise ValueError("MERCHANT_UPI_ID must be a valid UPI ID (contain @)")
        
        return True
    
    def get_plan(self, plan_id):
        """Get premium plan by ID"""
        return self.PREMIUM_PLANS.get(plan_id)
    
    def get_max_file_size(self, is_premium=False):
        """Get maximum file size based on user type"""
        return self.MAX_FILE_SIZE_PREMIUM if is_premium else self.MAX_FILE_SIZE_FREE
    
    def get_supported_extensions(self, file_type):
        """Get supported extensions for a file type"""
        return self.MEDIA_EXTENSIONS.get(file_type, [])
    
    def is_supported_media(self, filename):
        """Check if file is supported media type"""
        ext = os.path.splitext(filename)[1].lower()
        for extensions in self.MEDIA_EXTENSIONS.values():
            if ext in extensions:
                return True
        return False
    
    def get_file_type(self, filename):
        """Get file type based on extension"""
        ext = os.path.splitext(filename)[1].lower()
        for file_type, extensions in self.MEDIA_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        return 'other'

# Create global config instance
config = Config()

# Validation on import
try:
    config.validate_config()
    print("✅ Configuration validated successfully")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    raise
