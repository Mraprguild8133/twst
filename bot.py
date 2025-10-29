import os
import asyncio
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import logging

from config import Config
from wasabi_client import WasabiClient
from progress import Progress

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
app = Client(
    "wasabi_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

wasabi_client = WasabiClient()

# Start command
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    welcome_text = """
🤖 **Welcome to High-Speed File Storage Bot!**

**Features:**
✅ Upload files up to 5GB
✅ High-speed Wasabi cloud storage
✅ Direct streaming links
✅ MX Player & VLC support
✅ Fast download speeds

**Commands:**
/upload - Upload a file
/download - Download a file
/status - Check bot status
/help - Show this help message

**Supported Players:** MX Player, VLC, PotPlayer, and more!

**How to use:**
1. Send any file or use /upload command
2. Get direct streaming link
3. Use link with any media player
    """
    
    await message.reply_text(welcome_text)

# Upload command
@app.on_message(filters.command("upload") & filters.private)
async def upload_command(client, message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply_text("❌ Access denied. Admin only.")
        return
    
    await message.reply_text(
        "📤 **Upload File**\n\n"
        "Please send me the file you want to upload to Wasabi storage.\n"
        f"**Max file size:** 5GB\n"
        "**Supported formats:** All files\n\n"
        "I'll generate a direct streaming link for MX Player, VLC, and other players."
    )

# Download command
@app.on_message(filters.command("download") & filters.private)
async def download_command(client, message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply_text("❌ Access denied. Admin only.")
        return
    
    if len(message.command) < 2:
        await message.reply_text(
            "📥 **Download File**\n\n"
            "Usage: `/download filename`\n"
            "Example: `/download myvideo.mp4`\n\n"
            "To get available files, use /list"
        )
        return
    
    filename = ' '.join(message.command[1:])
    await handle_download(message, filename)

# List files command
@app.on_message(filters.command("list") & filters.private)
async def list_files_command(client, message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply_text("❌ Access denied. Admin only.")
        return
    
    await message.reply_text("📁 File listing feature will be implemented soon.\n\nFor now, please keep track of your uploaded filenames.")

# Status command
@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    status_text = """
🟢 **Bot Status: Online**

**Storage:** Wasabi Cloud
**Max File Size:** 5GB
**Streaming:** ✅ Supported
**Players:** MX Player, VLC, PotPlayer
**Speed:** High Performance

**Bot is ready to handle your files!**
    """
    await message.reply_text(status_text)

# Help command
@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    help_text = """
🆘 **Bot Help Guide**

**Available Commands:**
/start - Start the bot
/upload - Upload files to cloud storage  
/download - Download files from storage
/status - Check bot status
/help - This help message

**Upload Process:**
1. Use /upload command or send any file directly
2. Wait for upload to complete
3. Get direct streaming link
4. Copy link to any media player

**Download Process:**
1. Use /download filename.ext
2. File will be sent to you directly

**Streaming Instructions:**
• **MX Player:** Open app → Network Stream → Paste URL
• **VLC:** Media → Open Network Stream → Paste URL
• **Any Player:** Use the direct URL in network stream feature

**Supported File Types:**
• Videos (MP4, MKV, AVI, MOV, WEBM)
• Audio (MP3, M4A, FLAC, WAV) 
• Documents (PDF, DOC, TXT, ZIP)
• Images (JPG, PNG, GIF)
• All other file types
    """
    await message.reply_text(help_text)

# Handle file uploads
@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_file_upload(client, message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply_text("❌ Access denied. Admin only.")
        return
    
    # Get file information
    if message.document:
        file = message.document
        file_type = "document"
    elif message.video:
        file = message.video
        file_type = "video"
    elif message.audio:
        file = message.audio
        file_type = "audio"
    elif message.photo:
        file = message.photo
        file_type = "photo"
        # For photos, we need to get the largest size
        file = file.file_id
    else:
        return
    
    # Check file size
    if hasattr(file, 'file_size') and file.file_size > Config.MAX_FILE_SIZE:
        await message.reply_text(f"❌ File too large! Max size is 5GB.")
        return
    
    # Start upload process
    status_msg = await message.reply_text("🔄 Starting upload...")
    
    try:
        # Download file locally first
        if file_type == "photo":
            file_name = f"photo_{message.id}.jpg"
            download_path = f"downloads/{file_name}"
            # For photos, use different download method
            file_size = None
        else:
            file_name = getattr(file, 'file_name', f"{file_type}_{file.file_id}")
            download_path = f"downloads/{file.file_id}_{file_name}"
            file_size = file.file_size
        
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)
        
        # Download file from Telegram
        if file_type == "photo":
            await client.download_media(message, file_name=download_path)
            file_size = os.path.getsize(download_path)
        else:
            # Initialize progress tracking
            progress = Progress(client, status_msg, file_type)
            progress.set_total_size(file_size)
            
            await message.download(
                file_name=download_path,
                progress=progress.progress_callback,
                progress_args=(progress,)
            )
        
        # Upload to Wasabi
        await status_msg.edit_text("☁️ Uploading to Wasabi storage...")
        
        # Upload to Wasabi
        wasabi_url = await wasabi_client.upload_file(download_path, file_name)
        
        # Send success message with direct link
        success_text = f"""
✅ **Upload Successful!**

📁 **File Name:** `{file_name}`
💾 **File Size:** {format_size(file_size)}
🔗 **Direct URL:** `{wasabi_url}`

**🎬 Streaming Instructions:**

**For MX Player:**
1. Open MX Player
2. Go to Network Stream
3. Paste the URL above
4. Start streaming

**For VLC Player:**
1. Open VLC
2. Click Media → Open Network Stream
3. Paste the URL above
4. Click Play

**For Other Players:**
Use the direct URL in any media player that supports network streaming.

**📋 Quick Copy:**
```{wasabi_url}```
        """
        
        await status_msg.edit_text(success_text)
        
        # Also send the URL as a separate message for easy copying
        await message.reply_text(
            f"📋 **Direct URL for {file_name}:**\n\n`{wasabi_url}`\n\nCopy this URL to your media player.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Clean up local file
        try:
            os.remove(download_path)
        except Exception as e:
            logger.warning(f"Could not remove local file: {e}")
            
    except Exception as e:
        logger.error(f"Upload error: {e}")
        error_msg = f"❌ Upload failed: {str(e)}"
        await status_msg.edit_text(error_msg)
        
        # Clean up on error
        try:
            if 'download_path' in locals():
                os.remove(download_path)
        except:
            pass

# Handle downloads
async def handle_download(message: Message, filename: str):
    status_msg = await message.reply_text("🔍 Checking file availability...")
    
    try:
        # Check if file exists in Wasabi
        if not await wasabi_client.file_exists(filename):
            await status_msg.edit_text("❌ File not found in storage.")
            return
        
        # Download file
        download_path = f"downloads/{filename}"
        os.makedirs("downloads", exist_ok=True)
        
        await status_msg.edit_text("📥 Downloading from Wasabi...")
        
        # Download file
        local_path = await wasabi_client.download_file(filename, download_path)
        
        # Send file to user
        await status_msg.edit_text("📤 Sending file...")
        
        # Determine file type for sending
        if filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
            await message.reply_video(
                local_path, 
                caption=f"🎥 **{filename}**\n\n✅ Downloaded from cloud storage"
            )
        elif filename.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
            await message.reply_audio(
                local_path, 
                caption=f"🎵 **{filename}**\n\n✅ Downloaded from cloud storage"
            )
        elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            await message.reply_photo(
                local_path,
                caption=f"🖼️ **{filename}**\n\n✅ Downloaded from cloud storage"
            )
        else:
            await message.reply_document(
                local_path, 
                caption=f"📄 **{filename}**\n\n✅ Downloaded from cloud storage"
            )
        
        await status_msg.delete()
        
        # Clean up
        try:
            os.remove(local_path)
        except Exception as e:
            logger.warning(f"Could not remove downloaded file: {e}")
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ Download failed: {str(e)}")

# Utility functions
def format_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes is None:
        return "Unknown size"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

if __name__ == "__main__":
    print("🤖 Starting Telegram Wasabi Bot...")
    print("✅ No buttons version - Simple text interface")
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    app.run()
