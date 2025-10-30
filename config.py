import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Configuration
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Wasabi Configuration
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET")
    WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
    WASABI_ENDPOINT = f"https://s3.{WASABI_REGION}.wasabisys.com"
    
    # Premium Configuration
    ADMIN_IDS = [7619479679]  # Replace with your admin ID
    GPAY_UPI_ID = "your-upi-id@okaxis"  # Replace with your UPI ID
    PREMIUM_PRICE = 299  # INR
    
    # File size limits (4GB = 4 * 1024 * 1024 * 1024)
    MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
