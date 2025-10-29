import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Configuration
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    
    # Wasabi Configuration
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET")
    WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
    WASABI_ENDPOINT = f"https://s3.{WASABI_REGION}.wasabisys.com"
    
    # Bot Settings
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
    CHUNK_SIZE = 64 * 1024 * 1024  # 64MB chunks for large files
    DOWNLOAD_TIMEOUT = 3600  # 1 hour timeout for downloads
