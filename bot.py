import os
import time
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import boto3
from config import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
WASABI_ACCESS_KEY = config.WASABI_ACCESS_KEY
WASABI_SECRET_KEY = config.WASABI_SECRET_KEY
WASABI_BUCKET = config.WASABI_BUCKET
WASABI_REGION = config.WASABI_REGION
ADMIN_ID = config.ADMIN_ID

# Initialize bot
app = Client("wasabi_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=WASABI_ACCESS_KEY,
    aws_secret_access_key=WASABI_SECRET_KEY,
    endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com'
)

# Allowed users
ALLOWED_USERS = {ADMIN_ID}

def is_authorized(func):
    async def wrapper(client, message):
        if message.from_user.id in ALLOWED_USERS:
            await func(client, message)
        else:
            await message.reply_text("⛔️ You are not authorized.")
    return wrapper

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
        return "0B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

async def generate_presigned_url(filename):
    """Generate download link"""
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': filename},
            ExpiresIn=604800  # 7 days
        )
    except Exception as e:
        logger.error(f"URL generation failed: {e}")
        return None

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        f"🤖 **Wasabi Upload Bot**\n\n"
        f"Your ID: `{message.from_user.id}`\n\n"
        "Just send me any file to upload to Wasabi!"
    )

@app.on_message(filters.document | filters.video)
@is_authorized
async def handle_file(client, message):
    media = message.document or message.video
    file_name = media.file_name
    file_size = media.file_size

    status_msg = await message.reply_text("📥 Downloading file...")

    # Download file
    download_path = await client.download_media(message)
    
    await status_msg.edit_text("☁️ Uploading to Wasabi...")
    
    # Upload to Wasabi
    try:
        s3_client.upload_file(download_path, WASABI_BUCKET, file_name)
        
        # Generate download link
        download_url = await generate_presigned_url(file_name)
        
        if download_url:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📥 Download", url=download_url)
            ]])
            
            await status_msg.edit_text(
                f"✅ **Upload Successful!**\n\n"
                f"**File:** {file_name}\n"
                f"**Size:** {humanbytes(file_size)}\n"
                f"**Link expires in 7 days**",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text("❌ Failed to generate download link")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload failed: {str(e)}")
    
    # Cleanup
    if os.path.exists(download_path):
        os.remove(download_path)

@app.on_message(filters.command("adduser"))
async def add_user(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("⛔️ Admin only.")
        return
        
    try:
        user_id = int(message.text.split()[1])
        ALLOWED_USERS.add(user_id)
        await message.reply_text(f"✅ User {user_id} added.")
    except:
        await message.reply_text("Usage: /adduser <user_id>")

if __name__ == "__main__":
    print("🤖 Bot starting...")
    app.run()
