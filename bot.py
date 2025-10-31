# main.py
import os
import re
import asyncio
import time
import tempfile
import pathlib
import aiohttp
import aiofiles

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import config
from torrent_services import TorrentServiceManager

# --- Initialize Services ---
service_manager = TorrentServiceManager()

# --- Regex Patterns ---
TORRENT_REGEX = re.compile(
    r'(magnet:\?xt=urn:[a-z0-9]+:([a-z0-9]{32,40})&dn=|http[s]?://[^\s]*\.torrent)',
    re.IGNORECASE
)

# --- Pyrogram Client ---
if not config.validate():
    print("FATAL: Missing one or more required environment variables (API_ID, API_HASH, BOT_TOKEN).")
    exit(1)

app = Client(
    config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=10
)

# --- Utility Functions ---

def human_readable_bytes(size: int) -> str:
    """Converts bytes to a human-readable string."""
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"

def format_time(seconds: int) -> str:
    """Format seconds into human readable time"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

# --- Progress Callback ---

async def progress_callback(current: int, total: int, client: Client, message, start_time: float):
    """
    Asynchronous callback function to update the user on the upload progress.
    """
    elapsed = time.time() - start_time
    if elapsed == 0:
        elapsed = 0.1

    speed = current / elapsed
    percentage = current * 100 / total
    
    # Update every 3 seconds or when complete
    if (current == total) or (int(elapsed) % 3 == 0 and current > 0):
        try:
            # Create progress bar
            bar_length = 10
            filled_length = int(bar_length * current // total)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            # Calculate ETA
            if current > 0 and speed > 0:
                remaining = (total - current) / speed
                eta = format_time(int(remaining))
            else:
                eta = "Calculating..."
            
            upload_status = (
                f"**📤 Uploading File...**\n\n"
                f"**Progress:** `[{bar}] {percentage:.1f}%`\n"
                f"**Size:** `{human_readable_bytes(current)} / {human_readable_bytes(total)}`\n"
                f"**Speed:** `{human_readable_bytes(speed)}/s`\n"
                f"**Time Elapsed:** `{format_time(int(elapsed))}`\n"
                f"**ETA:** `{eta}`"
            )
            
            await message.edit_text(upload_status)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Progress update error: {e}")

# --- Bot Handlers ---

@app.on_message(filters.command("start"))
async def start_command(client: Client, message):
    """Handle /start command"""
    if not config.is_user_allowed(message.from_user.id):
        await message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    welcome_text = (
        "🤖 **Torrent Converter Bot**\n\n"
        "Send me a **magnet link** or **torrent URL** and I'll download and upload it to Telegram.\n\n"
        "**Features:**\n"
        "• Support for large files (4GB+)\n"
        "• Real-time progress updates\n"
        "• Multiple download services\n"
        "• Fast cloud downloading\n\n"
        "**Just send me a torrent link to get started!**"
    )
    
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help"))
async def help_command(client: Client, message):
    """Handle /help command"""
    help_text = (
        "**📖 How to use this bot:**\n\n"
        "1. Send a **magnet link** (starts with `magnet:?xt=urn:`)\n"
        "2. Or send a **.torrent file URL**\n"
        "3. The bot will download and upload the file to Telegram\n\n"
        "**Supported formats:**\n"
        "• Magnet links\n"
        "• Direct .torrent URLs\n\n"
        "**Note:** Large files may take time to upload. Please be patient!"
    )
    
    await message.reply_text(help_text)

@app.on_message(filters.private & filters.text)
async def handle_torrent_link(client: Client, message):
    """
    Handles incoming messages with torrent links
    """
    # Check user authorization
    if not config.is_user_allowed(message.from_user.id):
        await message.reply_text("❌ You are not authorized to use this bot.")
        return
    
    link = message.text.strip()
    
    # Check if it's a torrent link
    if not TORRENT_REGEX.match(link):
        await message.reply_text(
            "❌ Please send a valid **magnet link** or **torrent URL**.\n"
            "Use /help for more information."
        )
        return

    # Start processing
    status_message = await message.reply_text("🔎 Analyzing torrent link...")
    
    try:
        # Step 1: Download torrent via service manager
        await status_message.edit_text("🔄 Starting download process...")
        
        downloaded_file_path = await service_manager.download_torrent(link, status_message)
        
        if not downloaded_file_path:
            await status_message.edit_text("❌ Failed to download torrent. Please try again later.")
            return

        # Step 2: Prepare for upload
        file_stats = pathlib.Path(downloaded_file_path).stat()
        file_size = file_stats.st_size
        
        if file_size > config.MAX_FILE_SIZE:
            await status_message.edit_text(
                f"❌ File too large ({human_readable_bytes(file_size)}). "
                f"Maximum allowed size is {human_readable_bytes(config.MAX_FILE_SIZE)}."
            )
            os.remove(downloaded_file_path)
            return

        filename = os.path.basename(downloaded_file_path)
        start_time = time.time()

        # Step 3: Upload with progress
        await status_message.edit_text(
            f"**📤 Ready to Upload**\n\n"
            f"**File:** `{filename}`\n"
            f"**Size:** `{human_readable_bytes(file_size)}`\n"
            f"**Starting upload...**"
        )

        await client.send_document(
            chat_id=message.chat.id,
            document=downloaded_file_path,
            file_name=filename,
            caption=(
                f"✅ **Download Complete!**\n\n"
                f"**File:** `{filename}`\n"
                f"**Size:** `{human_readable_bytes(file_size)}`\n"
                f"**Converted from torrent link**"
            ),
            progress=progress_callback,
            progress_args=(client, status_message, start_time)
        )

        # Final success message
        total_time = int(time.time() - start_time)
        await status_message.edit_text(
            f"✅ **Upload Complete!**\n\n"
            f"**File:** `{filename}`\n"
            f"**Size:** `{human_readable_bytes(file_size)}`\n"
            f"**Total Time:** `{format_time(total_time)}`"
        )

    except FloodWait as e:
        await status_message.edit_text(f"⏳ Too many requests. Please wait {e.value} seconds and try again.")
    except RPCError as e:
        await status_message.edit_text(f"❌ Telegram API error: {str(e)}")
    except Exception as e:
        await status_message.edit_text(f"❌ Unexpected error: {str(e)}")
        print(f"Error in handle_torrent_link: {e}")
    finally:
        # Cleanup
        if 'downloaded_file_path' in locals() and downloaded_file_path and os.path.exists(downloaded_file_path):
            try:
                os.remove(downloaded_file_path)
                temp_dir = os.path.dirname(downloaded_file_path)
                if temp_dir.startswith(tempfile.gettempdir()):
                    os.rmdir(temp_dir)
            except Exception as e:
                print(f"Cleanup error: {e}")

@app.on_message(filters.private & filters.document)
async def handle_direct_upload(client: Client, message):
    """Handle direct .torrent file uploads"""
    if not config.is_user_allowed(message.from_user.id):
        return
        
    if message.document and message.document.file_name and message.document.file_name.endswith('.torrent'):
        await message.reply_text("📥 .torrent file received! Processing...\n\n*Note: Direct .torrent file processing requires additional setup.*")

# --- Error Handler ---

@app.on_error()
async def error_handler(_, update, error):
    """Global error handler"""
    print(f"Error in update {update}: {error}")
    # You can add specific error handling logic here

# --- Main Execution ---

if __name__ == "__main__":
    print("🤖 Torrent Converter Bot Starting...")
    print(f"API ID: {config.API_ID} | Bot Token: {config.BOT_TOKEN[:10]}...")
    print(f"Max File Size: {human_readable_bytes(config.MAX_FILE_SIZE)}")
    print(f"Allowed Users: {config.ALLOWED_USER_IDS if config.ALLOWED_USER_IDS else 'All'}")
    print("Bot is running. Press Ctrl+C to stop.")
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
