import asyncio
import os
import time
import logging
from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import timedelta

# Import from config
from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS,
    WASABI_ACCESS_KEY, WASABI_SECRET_KEY, WASABI_BUCKET, 
    WASABI_REGION, WASABI_ENDPOINT_URL, MAX_FILE_SIZE,
    STREAM_EXPIRATION, TEMP_DIR
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Pyrogram Client Initialization ---
app = Client(
    "wasabi_file_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# --- Wasabi/Boto3 Client Initialization ---
s3_config = Config(
    region_name=WASABI_REGION,
    signature_version='s3v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)

wasabi_client = boto3.client(
    's3',
    endpoint_url=WASABI_ENDPOINT_URL,
    aws_access_key_id=WASABI_ACCESS_KEY,
    aws_secret_access_key=WASABI_SECRET_KEY,
    config=s3_config
)

# --- Helper Functions ---

async def upload_file_to_wasabi(file_path: str, wasabi_key: str):
    """
    Asynchronously uploads a file from a local path to Wasabi.
    """
    logger.info(f"Starting Wasabi upload for key: {wasabi_key}")
    
    with open(file_path, 'rb') as data:
        try:
            await asyncio.to_thread(
                wasabi_client.upload_fileobj,
                data,
                WASABI_BUCKET,
                wasabi_key,
                ExtraArgs={'ContentType': 'application/octet-stream'}
            )
            logger.info(f"Wasabi upload successful for key: {wasabi_key}")
            return True
        except ClientError as e:
            logger.error(f"Wasabi upload failed for key {wasabi_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            return False

async def generate_presigned_url(wasabi_key: str, expiration_seconds: int = 3600):
    """
    Asynchronously generates a pre-signed URL for high-speed download streaming.
    """
    logger.info(f"Generating presigned URL for key: {wasabi_key}")
    try:
        url = await asyncio.to_thread(
            wasabi_client.generate_presigned_url,
            'get_object',
            Params={
                'Bucket': WASABI_BUCKET,
                'Key': wasabi_key
            },
            ExpiresIn=expiration_seconds
        )
        logger.info("Presigned URL generated successfully.")
        return url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {wasabi_key}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating URL: {e}")
        return None

# --- Pyrogram Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    """Handles the /start command."""
    await message.reply_text(
        "👋 Hello! I am a high-speed file storage and streaming bot.\n\n"
        "**Features:**\n"
        "• Upload files up to 4GB to Wasabi storage\n"
        "• Generate high-speed streaming links\n"
        "• Direct S3 integration for maximum performance\n\n"
        "Just send me any file (document, video, or audio) and I'll handle the rest!"
    )

@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client, message):
    """Shows bot statistics and info."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    stats_text = (
        "🤖 **Bot Statistics**\n\n"
        f"**Admin IDs:** {len(ADMIN_IDS)}\n"
        f"**Wasabi Bucket:** {WASABI_BUCKET}\n"
        f"**Wasabi Region:** {WASABI_REGION}\n"
        f"**Max File Size:** {MAX_FILE_SIZE / (1024**3):.0f} GB\n"
        f"**Stream Expiration:** {STREAM_EXPIRATION / 3600:.0f} hours\n"
        f"**Temp Directory:** {TEMP_DIR}\n"
    )
    await message.reply_text(stats_text)

@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def upload_handler(client, message: types.Message):
    """
    Handles incoming files, downloads them to a temporary location, 
    uploads them to Wasabi, and generates a streaming link.
    """
    
    # 1. Admin Check
    if message.from_user.id not in ADMIN_IDS:
        await message.reply_text("🚫 You are not authorized to use this feature.")
        return
        
    # 2. Extract File Info
    if message.document:
        file_info = message.document
    elif message.video:
        file_info = message.video
    elif message.audio:
        file_info = message.audio
    else:
        await message.reply_text("Please send a document, video, or audio file.")
        return
    
    file_size = file_info.file_size
    file_name = file_info.file_name or f"file_{file_info.file_id}"
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ File size ({file_size / (1024**3):.2f} GB) exceeds the {MAX_FILE_SIZE / (1024**3):.0f}GB limit."
        )
        return

    # 3. Inform User and Start Download
    status_msg = await message.reply_text(
        f"📥 **Downloading File**\n"
        f"**Name:** `{file_name}`\n"
        f"**Size:** {file_size / (1024**2):.2f} MB\n"
        f"**Status:** Starting download...",
        quote=True
    )
    
    temp_file_path = None
    start_time = time.time()
    
    try:
        # Create safe temporary file path
        safe_filename = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        temp_file_path = os.path.join(TEMP_DIR, f"temp_{message.id}_{safe_filename}")
        
        # Download file
        logger.info(f"Downloading file to: {temp_file_path}")
        download_start = time.time()
        await client.download_media(message, file_name=temp_file_path)
        
        download_time = time.time() - download_start
        download_speed = file_size / (1024 * 1024) / download_time if download_time > 0 else 0
        
        await status_msg.edit_text(
            f"📥 **Download Complete**\n"
            f"**Name:** `{file_name}`\n"
            f"**Speed:** {download_speed:.2f} MB/s\n"
            f"**Status:** Uploading to Wasabi...",
        )
        
        # 4. Upload to Wasabi
        wasabi_key = f"telegram/{message.from_user.id}/{file_name}_{file_info.file_unique_id}"
        
        upload_start = time.time()
        upload_success = await upload_file_to_wasabi(temp_file_path, wasabi_key)
        
        if upload_success:
            upload_time = time.time() - upload_start
            upload_speed = file_size / (1024 * 1024) / upload_time if upload_time > 0 else 0
            
            # 5. Generate Streaming Link
            streaming_url = await generate_presigned_url(wasabi_key, STREAM_EXPIRATION)
            
            if streaming_url:
                total_time = time.time() - start_time
                await status_msg.edit_text(
                    f"🎉 **Upload Complete!**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Size:** {file_size / (1024**2):.2f} MB\n"
                    f"**Download Speed:** {download_speed:.2f} MB/s\n"
                    f"**Upload Speed:** {upload_speed:.2f} MB/s\n"
                    f"**Total Time:** {total_time:.2f}s\n\n"
                    f"🔗 **Streaming Link (Expires in {timedelta(seconds=STREAM_EXPIRATION)}):**\n"
                    f"`{streaming_url}`\n\n"
                    f"💡 *You can share this link for high-speed direct streaming!*",
                    disable_web_page_preview=True
                )
            else:
                await status_msg.edit_text(
                    "⚠️ File uploaded to Wasabi, but failed to generate streaming link.\n"
                    "Please try again or check the bot logs."
                )
        else:
            await status_msg.edit_text(
                "❌ Failed to upload file to Wasabi storage.\n"
                "Please check your Wasabi configuration or try again later."
            )
            
    except FloodWait as e:
        logger.warning(f"FloodWait: sleeping for {e.value} seconds")
        await status_msg.edit_text(
            f"⏳ Telegram flood control active. Waiting {e.value} seconds..."
        )
        await asyncio.sleep(e.value)
        await status_msg.edit_text("❌ Operation failed due to flood wait. Please try again later.")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ An unexpected error occurred:\n`{str(e)}`\n\nPlease try again later."
        )

    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                await asyncio.to_thread(os.remove, temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                logger.error(f"Error cleaning up temporary file: {e}")

@app.on_message(filters.command("cleanup") & filters.private)
async def cleanup_command(client, message):
    """Clean up temporary files (admin only)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    try:
        # Count and remove temporary files
        temp_files = [f for f in os.listdir(TEMP_DIR) if f.startswith('temp_')]
        for file in temp_files:
            file_path = os.path.join(TEMP_DIR, file)
            await asyncio.to_thread(os.remove, file_path)
        
        await message.reply_text(f"🧹 Cleaned up {len(temp_files)} temporary files.")
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        await message.reply_text(f"❌ Cleanup failed: {e}")

# --- Main Entry Point ---
if __name__ == "__main__":
    logger.info("Starting Telegram Bot Client...")
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    logger.info(f"Wasabi Bucket: {WASABI_BUCKET}")
    logger.info(f"Temp Directory: {TEMP_DIR}")
    
    # Create temp directory if it doesn't exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    app.run()
