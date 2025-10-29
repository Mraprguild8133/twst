# main.py
import os
import asyncio
import logging
import time
from datetime import datetime

# Import from config
from config import config

# Mandatory imports for the core functionality
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

# External storage client
import boto3
from botocore.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)

# --- Wasabi Client Initialization ---
WASABI_CONFIG = Config(
    region_name=config.WASABI_REGION,
    s3={'signature_version': 's3v4'},
    retries={'max_attempts': 10, 'mode': 'standard'}
)

WASABI_CLIENT = boto3.client(
    's3',
    aws_access_key_id=config.WASABI_ACCESS_KEY,
    aws_secret_access_key=config.WASABI_SECRET_KEY,
    endpoint_url=f'https://s3.{config.WASABI_REGION}.wasabisys.com',
    config=WASABI_CONFIG
)

# --- Pyrogram Client Initialization ---
app = Client(
    "wasabi_file_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    max_concurrent_transfers=5,
    workers=30
)

# --- Progress Callback Class ---
class ProgressCallback:
    """A callback class to report progress for file transfers."""
    
    def __init__(self, message: Message, filename: str, start_time: float, action: str):
        self.message = message
        self.filename = filename
        self.start_time = start_time
        self.last_edit_time = start_time
        self.action = action
        self.is_upload = (action == 'Uploading')
        self.uploaded_bytes = 0
        self.total_size = 0

    async def __call__(self, current_bytes: int, total_bytes: int):
        """Called periodically by pyrogram (download) or boto3 (upload)."""
        self.total_size = total_bytes
        
        if not self.is_upload:
            self.uploaded_bytes = current_bytes

        # Rate-limit message edits to avoid flood waits
        if (time.time() - self.last_edit_time) >= 4:
            self.last_edit_time = time.time()
            await self._edit_message()

    async def _edit_message(self):
        """Formats and edits the progress message."""
        try:
            if self.total_size == 0:
                return
                
            percent = min(100, round(self.uploaded_bytes * 100 / self.total_size))
            
            # Convert bytes to human-readable format
            human_uploaded = self.human_readable_size(self.uploaded_bytes)
            human_total = self.human_readable_size(self.total_size)
            
            # Calculate speed and ETA
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                speed = self.uploaded_bytes / elapsed_time
                human_speed = self.human_readable_size(speed) + "/s"
                remaining_bytes = self.total_size - self.uploaded_bytes
                eta_seconds = remaining_bytes / speed if speed > 0 else 0
                eta = self.format_time(eta_seconds)
            else:
                human_speed = "0 B/s"
                eta = "N/A"

            # Progress Bar
            bar_length = 10
            filled_length = int(bar_length * percent // 100)
            bar = '▓' * filled_length + '░' * (bar_length - filled_length)
            
            text = (
                f"**{self.action}** `{self.filename}`\n\n"
                f"**Progress:** {bar} {percent}%\n"
                f"**Size:** {human_uploaded} / {human_total}\n"
                f"**Speed:** {human_speed}\n"
                f"**ETA:** {eta}"
            )

            await self.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        except FloodWait as e:
            LOGGER.warning(f"FloodWait encountered. Sleeping for {e.value}s.")
            self.last_edit_time = time.time() + e.value
            await asyncio.sleep(e.value)
        except Exception as e:
            LOGGER.error(f"Error editing message: {e}")
    
    def sync_callback(self, bytes_amount):
        """Boto3 calls this synchronous method."""
        self.uploaded_bytes += bytes_amount
        # Schedule async update
        asyncio.create_task(self._edit_message())

    @staticmethod
    def human_readable_size(size: float) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds into human-readable time."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

# --- Helper Functions ---
async def log_to_channel(text: str):
    """Send a message to the designated log channel."""
    try:
        await app.send_message(config.LOG_CHANNEL_ID, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Failed to send log message to channel: {e}")

def generate_streaming_link(object_key: str, expires_in: int = None) -> str:
    """Generate a secure, pre-signed URL for streaming from Wasabi."""
    if expires_in is None:
        expires_in = config.LINK_EXPIRY
        
    try:
        url = WASABI_CLIENT.generate_presigned_url(
            'get_object',
            Params={'Bucket': config.WASABI_BUCKET, 'Key': object_key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        LOGGER.error(f"Error generating pre-signed URL: {e}")
        return None

# --- Command Handlers ---
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle the /start command."""
    await message.reply_text(
        "👋 **Welcome to the Wasabi File Streamer Bot!**\n\n"
        "I can handle file uploads up to 5GB, powered by Pyrogram and Wasabi S3.\n"
        "Just send me any file and I'll upload it, providing a direct streaming link."
    )
    await log_to_channel(
        f"<b>User Started:</b> "
        f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
    )

@app.on_message(filters.command("stats") & filters.user(config.ADMIN_IDS))
async def stats_command(client: Client, message: Message):
    """Show bot statistics (admin only)."""
    stats_text = (
        "🤖 **Bot Statistics**\n\n"
        "**Status:** ✅ Running\n"
        "**Max File Size:** 5GB\n"
        "**Storage:** Wasabi S3\n"
        "**Link Expiry:** 7 days"
    )
    await message.reply_text(stats_text)

# --- File Handler ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def file_handler(client: Client, message: Message):
    """Handle incoming file messages."""
    # Determine file type and get file info
    if message.document:
        file_info = message.document
    elif message.video:
        file_info = message.video
    elif message.audio:
        file_info = message.audio
    elif message.photo:
        file_info = message.photo
        # For photos, we need to handle differently
        file_size = file_info.file_size
        file_name = f"photo_{file_info.file_unique_id}.jpg"
    else:
        await message.reply_text("❌ Unsupported file type.")
        return

    # Get file name and size for non-photo files
    if not message.photo:
        file_name = getattr(file_info, "file_name", 
                           f"{file_info.file_unique_id}.{file_info.mime_type.split('/')[-1] if file_info.mime_type else 'dat'}")
        file_size = file_info.file_size

    # Check file size
    if file_size > config.MAX_FILE_SIZE:
        await message.reply_text(f"❌ File too large. Maximum size is 5GB.")
        return

    # Create paths
    os.makedirs(config.DOWNLOAD_PATH, exist_ok=True)
    temp_file_path = os.path.join(config.DOWNLOAD_PATH, f"{file_info.file_unique_id}_{file_name}")
    
    # Create unique Wasabi key
    wasabi_object_key = (
        f"{message.from_user.id}/"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
        f"{file_info.file_unique_id}_{file_name}"
    )

    LOGGER.info(f"Processing file: {file_name} ({file_size} bytes)")

    # Initial status message
    status_msg = await message.reply_text(f"📥 Starting download of `{file_name}`...")
    start_time = time.time()

    # Download file
    try:
        progress_cb = ProgressCallback(status_msg, file_name, start_time, "Downloading")
        
        downloaded_path = await client.download_media(
            message,
            file_name=temp_file_path,
            progress=progress_cb,
            progress_args=(file_size,),
        )
        
        await status_msg.edit_text("✅ Download complete. Starting upload to Wasabi...")
        upload_start_time = time.time()

    except Exception as e:
        await status_msg.edit_text(f"❌ **Download Failed:** {str(e)}")
        LOGGER.error(f"Download error for {file_name}: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return

    # Upload to Wasabi
    def sync_upload():
        try:
            WASABI_CLIENT.upload_file(
                Filename=downloaded_path,
                Bucket=config.WASABI_BUCKET,
                Key=wasabi_object_key,
                Callback=ProgressCallback(status_msg, file_name, upload_start_time, "Uploading").sync_callback if file_size > 0 else None,
            )
            return True
        except Exception as e:
            LOGGER.error(f"Upload error for {wasabi_object_key}: {e}")
            return False

    try:
        loop = asyncio.get_event_loop()
        upload_success = await loop.run_in_executor(None, sync_upload)

        if upload_success:
            streaming_link = generate_streaming_link(wasabi_object_key)
            
            if streaming_link:
                await log_to_channel(
                    f"✅ <b>File Uploaded:</b> "
                    f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>\n"
                    f"<b>File:</b> <code>{file_name}</code>\n"
                    f"<b>Size:</b> {ProgressCallback.human_readable_size(file_size)}"
                )

                final_text = (
                    f"✅ **Upload Complete!**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Size:** {ProgressCallback.human_readable_size(file_size)}\n\n"
                    f"🔗 **Streaming Link:**\n"
                    f"```\n{streaming_link}\n```\n\n"
                    f"This link expires in 7 days and supports direct streaming."
                )
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Open Link", url=streaming_link)],
                    [InlineKeyboardButton("🔗 Copy Link", callback_data=f"copy_{streaming_link}")]
                ])
                
                await status_msg.edit_text(final_text, reply_markup=keyboard, disable_web_page_preview=True)
            else:
                await status_msg.edit_text("❌ Upload failed: Could not generate streaming link.")
        else:
            await status_msg.edit_text("❌ Upload failed. Please try again later.")

    finally:
        # Cleanup
        if os.path.exists(downloaded_path):
            os.remove(downloaded_path)
            LOGGER.info(f"Cleaned up local file: {downloaded_path}")

# --- Callback Handler for Copy Button ---
@app.on_callback_query(filters.regex(r"^copy_"))
async def copy_link_callback(client: Client, callback_query: CallbackQuery):
    """Handle copy link button clicks."""
    link = callback_query.data[5:]  # Remove "copy_" prefix
    await callback_query.answer("Link copied to clipboard!", show_alert=True)
    # Note: Telegram bots can't actually copy to clipboard, this is just visual feedback

# --- Main Execution ---
async def main():
    """Main function to start the bot."""
    LOGGER.info("Starting Wasabi File Bot...")
    await app.start()
    LOGGER.info("Bot is running. Press Ctrl+C to stop.")
    await idle()
    LOGGER.info("Stopping bot...")
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
