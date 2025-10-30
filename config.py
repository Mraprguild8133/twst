# config.py
import os
from typing import List

# Telegram API Configuration
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Admin Configuration
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "123456789")
ADMIN_IDS = [int(i.strip()) for i in ADMIN_IDS_STR.split(',') if i.strip().isdigit()]

# Wasabi Configuration
WASABI_ACCESS_KEY = os.environ.get("WASABI_ACCESS_KEY", "YOUR_WASABI_ACCESS_KEY")
WASABI_SECRET_KEY = os.environ.get("WASABI_SECRET_KEY", "YOUR_WASABI_SECRET_KEY")
WASABI_BUCKET = os.environ.get("WASABI_BUCKET", "your-wasabi-bucket")
WASABI_REGION = os.environ.get("WASABI_REGION", "us-east-1")
WASABI_ENDPOINT_URL = f"https://s3.{WASABI_REGION}.wasabisys.com"

# Bot Configuration
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB
STREAM_EXPIRATION = 24 * 3600  # 24 hours
TEMP_DIR = os.path.join(os.getcwd(), "temp_files")

# Create temp directory if it doesn't exist
os.makedirs(TEMP_DIR, exist_ok=True)
