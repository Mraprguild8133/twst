import os
import asyncio
import logging
import shutil
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageMediaType
import boto3
from botocore.exceptions import ClientError
import aiofiles
import hashlib
import time

from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure temp directory exists
os.makedirs(config.TEMP_DIR, exist_ok=True)

# Initialize Wasabi S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=config.WASABI_ENDPOINT,
    aws_access_key_id=config.WASABI_ACCESS_KEY,
    aws_secret_access_key=config.WASABI_SECRET_KEY,
    region_name=config.WASABI_REGION
)

# Initialize Telegram client
app = Client(
    "wasabi_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

class ProgressTracker:
    def __init__(self, message: Message, operation: str):
        self.message = message
        self.operation = operation
        self.start_time = time.time()
        self.last_update = 0
        
    async def update_progress(self, current, total):
        # Update progress every 2 seconds to avoid spam
        if time.time() - self.last_update < 2 and current != total:
            return
            
        self.last_update = time.time()
        
        percentage = (current / total) * 100
        speed = current / (time.time() - self.start_time) if time.time() > self.start_time else 0
        elapsed = time.time() - self.start_time
        
        speed_str = self._format_size(speed) + "/s" if speed > 0 else "0 B/s"
        progress_bar = self._create_progress_bar(percentage)
        
        text = (
            f"**{self.operation} Progress**\n\n"
            f"`{progress_bar}` {percentage:.1f}%\n"
            f"**Size:** {self._format_size(current)} / {self._format_size(total)}\n"
            f"**Speed:** {speed_str}\n"
            f"**Elapsed:** {self._format_time(elapsed)}"
        )
        
        try:
            await self.message.edit_text(text)
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")
    
    def _format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names)-1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def _format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _create_progress_bar(self, percentage, length=20):
        filled = int(length * percentage // 100)
        empty = length - filled
        return "█" * filled + "░" * empty

async def generate_presigned_url(bucket_name: str, object_name: str, expiration: int = None) -> str:
    """Generate a presigned URL for Wasabi object"""
    if expiration is None:
        expiration = config.URL_EXPIRATION
        
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        raise

async def upload_to_wasabi(file_path: str, object_name: str, progress_tracker: ProgressTracker) -> bool:
    """Upload file to Wasabi storage with progress tracking"""
    try:
        file_size = os.path.getsize(file_path)
        
        # Upload with progress
        def progress_callback(bytes_transferred):
            asyncio.create_task(progress_tracker.update_progress(bytes_transferred, file_size))
        
        s3_client.upload_file(
            file_path,
            config.WASABI_BUCKET,
            object_name,
            Callback=progress_callback
        )
        
        return True
    except Exception as e:
        logger.error(f"Error uploading to Wasabi: {e}")
        return False

async def download_from_wasabi(object_name: str, file_path: str, progress_tracker: ProgressTracker) -> bool:
    """Download file from Wasabi storage with progress tracking"""
    try:
        # Get object size first
        response = s3_client.head_object(Bucket=config.WASABI_BUCKET, Key=object_name)
        file_size = response['ContentLength']
        
        # Download with progress
        def progress_callback(bytes_transferred):
            asyncio.create_task(progress_tracker.update_progress(bytes_transferred, file_size))
        
        s3_client.download_file(
            config.WASABI_BUCKET,
            object_name,
            file_path,
            Callback=progress_callback
        )
        
        return True
    except Exception as e:
        logger.error(f"Error downloading from Wasabi: {e}")
        return False

def generate_file_id(file_name: str, user_id: int) -> str:
    """Generate unique file ID for Wasabi storage"""
    timestamp = str(int(time.time()))
    unique_string = f"{user_id}_{file_name}_{timestamp}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def cleanup_temp_file(file_path: str):
    """Clean up temporary files"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file {file_path}: {e}")

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handle /start command"""
    welcome_text = """
🤖 **Welcome to Wasabi Storage Bot!**

I can help you:
• 📤 Upload files to Wasabi cloud storage (up to 4GB)
• 📥 Download files from Wasabi
• 🔗 Generate shareable streaming links
• ⚡ High-speed file transfers

**Commands:**
/upload - Upload a file
/download - Download a file
/list - List your files
/help - Show this help message

Just send me any file or use the commands above!
    """
    
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Handle /help command"""
    help_text = """
📖 **Bot Help Guide**

**How to upload files:**
1. Send any file to the bot (up to 4GB)
2. Or use /upload command
3. The bot will upload to Wasabi storage
4. You'll get a shareable streaming link

**How to download files:**
1. Use /download command with file key
2. Or click on download button from previous uploads

**Features:**
• 🚀 High-speed transfers
• ☁️ Wasabi cloud storage
• 🔗 Temporary streaming links
• 📊 Real-time progress
• 🔒 Secure file handling

**Supported file types:** All types!
    """
    
    await message.reply_text(help_text)

@app.on_message(filters.media | filters.document)
async def handle_files(client, message: Message):
    """Handle incoming files for upload"""
    if not (message.media or message.document):
        await message.reply_text("❌ Please send a valid file.")
        return
    
    # Check file size
    if message.document and message.document.file_size > config.MAX_FILE_SIZE:
        await message.reply_text(f"❌ File too large. Maximum size is 4GB.")
        return
    
    # Send initial message
    status_msg = await message.reply_text("🔄 Starting upload process...")
    download_path = None
    
    try:
        # Generate unique file ID
        file_name = message.document.file_name if message.document else "file"
        file_id = generate_file_id(file_name, message.from_user.id)
        object_name = f"telegram/{message.from_user.id}/{file_id}_{file_name}"
        download_path = os.path.join(config.TEMP_DIR, f"temp_{file_id}")
        
        # Download file from Telegram
        progress_tracker = ProgressTracker(status_msg, "Downloading from Telegram")
        
        await message.download(
            file_name=download_path,
            progress=progress_tracker.update_progress,
            progress_args=(progress_tracker,)
        )
        
        # Upload to Wasabi
        await status_msg.edit_text("☁️ Uploading to Wasabi storage...")
        upload_progress = ProgressTracker(status_msg, "Uploading to Wasabi")
        
        success = await upload_to_wasabi(download_path, object_name, upload_progress)
        
        if success:
            # Generate streaming link
            streaming_url = await generate_presigned_url(config.WASABI_BUCKET, object_name)
            
            # Create keyboard with actions
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Streaming Link", url=streaming_url)],
                [InlineKeyboardButton("📥 Download", callback_data=f"download_{object_name}")],
                [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{object_name}")]
            ])
            
            await status_msg.edit_text(
                f"✅ **File Uploaded Successfully!**\n\n"
                f"**File Name:** `{file_name}`\n"
                f"**Storage Key:** `{object_name}`\n"
                f"**Link Expires:** {config.URL_EXPIRATION // 3600} hours\n\n"
                f"Use the buttons below to manage your file:",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text("❌ Failed to upload file to Wasabi storage.")
            
    except Exception as e:
        logger.error(f"Error handling file: {e}")
        await status_msg.edit_text(f"❌ Error processing file: {str(e)}")
    finally:
        # Cleanup temp file
        if download_path and os.path.exists(download_path):
            cleanup_temp_file(download_path)

@app.on_message(filters.command("upload"))
async def upload_command(client, message: Message):
    """Handle /upload command"""
    await message.reply_text("📤 Please send me the file you want to upload to Wasabi storage.")

@app.on_message(filters.command("download"))
async def download_command(client, message: Message):
    """Handle /download command"""
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a file key. Usage: `/download <file_key>`")
        return
    
    file_key = message.command[1]
    status_msg = await message.reply_text("🔄 Starting download process...")
    download_path = None
    
    try:
        # Check if file exists
        try:
            s3_client.head_object(Bucket=config.WASABI_BUCKET, Key=file_key)
        except ClientError:
            await status_msg.edit_text("❌ File not found in storage.")
            return
        
        # Download file
        file_name = file_key.split('_')[-1] if '_' in file_key else "downloaded_file"
        download_path = os.path.join(config.TEMP_DIR, f"dl_{generate_file_id(file_name, message.from_user.id)}")
        
        progress_tracker = ProgressTracker(status_msg, "Downloading from Wasabi")
        success = await download_from_wasabi(file_key, download_path, progress_tracker)
        
        if success:
            await status_msg.edit_text("📤 Uploading to Telegram...")
            
            # Upload to Telegram
            upload_progress = ProgressTracker(status_msg, "Uploading to Telegram")
            
            await message.reply_document(
                document=download_path,
                file_name=file_name,
                progress=upload_progress.update_progress,
                progress_args=(upload_progress,)
            )
            
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Failed to download file from Wasabi.")
            
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        await status_msg.edit_text(f"❌ Error downloading file: {str(e)}")
    finally:
        # Cleanup temp file
        if download_path and os.path.exists(download_path):
            cleanup_temp_file(download_path)

@app.on_callback_query(filters.regex(r"^download_"))
async def handle_download_callback(client, callback_query):
    """Handle download button clicks"""
    file_key = callback_query.data.replace("download_", "")
    await callback_query.answer("Starting download...")
    await download_command(client, callback_query.message)

@app.on_callback_query(filters.regex(r"^delete_"))
async def handle_delete_callback(client, callback_query):
    """Handle delete button clicks"""
    file_key = callback_query.data.replace("delete_", "")
    
    try:
        s3_client.delete_object(Bucket=config.WASABI_BUCKET, Key=file_key)
        await callback_query.answer("File deleted successfully!")
        await callback_query.message.edit_text("🗑️ File has been deleted from storage.")
    except Exception as e:
        await callback_query.answer("Error deleting file!")
        logger.error(f"Error deleting file: {e}")

def main():
    """Main function to start the bot"""
    try:
        # Validate configuration
        config.validate_config()
        logger.info("Configuration validated successfully")
        
        # Start the bot
        logger.info("Starting Telegram Wasabi Bot...")
        app.run()
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
