import os
import asyncio
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
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
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Upload File", callback_data="upload_help")],
        [InlineKeyboardButton("📥 Download File", callback_data="download_help")],
        [InlineKeyboardButton("🌐 Supported Players", callback_data="players_info")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=keyboard)

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
            "Example: `/download myvideo.mp4`"
        )
        return
    
    filename = message.command[1]
    await handle_download(message, filename)

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
    """
    await message.reply_text(status_text)

# Handle file uploads
@app.on_message(filters.document | filters.video | filters.audio)
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
    else:
        return
    
    # Check file size
    if file.file_size > Config.MAX_FILE_SIZE:
        await message.reply_text(f"❌ File too large! Max size is 5GB.")
        return
    
    # Start upload process
    status_msg = await message.reply_text("🔄 Starting upload...")
    
    try:
        # Download file locally first
        file_name = file.file_name or f"{file_type}_{file.file_id}"
        download_path = f"downloads/{file.file_id}_{file_name}"
        
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)
        
        # Initialize progress tracking
        progress = Progress(client, status_msg, file_type)
        progress.set_total_size(file.file_size)
        
        # Download file from Telegram
        await message.download(
            file_name=download_path,
            progress=progress.progress_callback,
            progress_args=(progress,)
        )
        
        # Upload to Wasabi
        await status_msg.edit_text("☁️ Uploading to Wasabi storage...")
        
        wasabi_progress = Progress(client, status_msg, file_type)
        wasabi_progress.set_total_size(file.file_size)
        
        # Upload to Wasabi
        wasabi_url = await wasabi_client.upload_file(
            download_path,
            file_name,
            progress_callback=wasabi_progress.progress_callback
        )
        
        # Generate streaming links
        streaming_links = generate_streaming_links(wasabi_url, file_name)
        
        # Send success message with links
        success_text = f"""
✅ **Upload Successful!**

📁 **File:** `{file_name}`
💾 **Size:** {format_size(file.file_size)}
🔗 **Direct URL:** {wasabi_url}

**🎬 Streaming Links:**
{streaming_links}

**📱 Supported Players:**
• MX Player: Copy direct URL
• VLC: Open network stream
• PotPlayer: Open URL
• Any modern media player
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Direct Link", url=wasabi_url)],
            [InlineKeyboardButton("📱 MX Player", url=f"intent:{wasabi_url}#Intent;package=com.mxtech.videoplayer.ad;end")],
            [InlineKeyboardButton("▶️ VLC", url=f"vlc://{wasabi_url}")],
            [InlineKeyboardButton("🔄 Share", switch_inline_query=file_name)]
        ])
        
        await status_msg.edit_text(success_text, reply_markup=keyboard)
        
        # Clean up local file
        try:
            os.remove(download_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await status_msg.edit_text(f"❌ Upload failed: {str(e)}")
        
        # Clean up on error
        try:
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
        
        # Download file (progress would be implemented similarly to upload)
        local_path = await wasabi_client.download_file(filename, download_path)
        
        # Send file to user
        await status_msg.edit_text("📤 Sending file...")
        
        # Determine file type for sending
        if filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
            await message.reply_video(local_path, caption=f"📥 {filename}")
        elif filename.lower().endswith(('.mp3', '.m4a', '.flac', '.wav')):
            await message.reply_audio(local_path, caption=f"🎵 {filename}")
        else:
            await message.reply_document(local_path, caption=f"📄 {filename}")
        
        await status_msg.delete()
        
        # Clean up
        try:
            os.remove(local_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ Download failed: {str(e)}")

# Callback query handler
@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    data = callback_query.data
    
    if data == "upload_help":
        await callback_query.message.edit_text(
            "📤 **How to Upload:**\n\n"
            "1. Send any file (document, video, audio)\n"
            "2. Wait for upload to complete\n"
            "3. Get direct streaming links\n"
            "4. Use with MX Player, VLC, etc.\n\n"
            "**Max file size:** 5GB\n"
            "**Supported:** All file types",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
            ])
        )
    
    elif data == "download_help":
        await callback_query.message.edit_text(
            "📥 **How to Download:**\n\n"
            "Use command: `/download filename.ext`\n\n"
            "Example: `/download myvideo.mp4`\n\n"
            "The file must already be in storage.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
            ])
        )
    
    elif data == "players_info":
        await callback_query.message.edit_text(
            "🎬 **Supported Players:**\n\n"
            "• **MX Player** - Direct URL support\n"
            "• **VLC Media Player** - Network stream\n"
            "• **PotPlayer** - URL playback\n"
            "• **KM Player** - Stream support\n"
            "• **All modern media players**\n\n"
            "Just copy the direct link and paste in your player!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
            ])
        )
    
    elif data == "back_to_start":
        await start_command(client, callback_query.message)

# Utility functions
def format_size(size_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def generate_streaming_links(direct_url, filename):
    """Generate streaming links for different players"""
    links = []
    
    # MX Player intent
    mx_player_link = f"intent:{direct_url}#Intent;package=com.mxtech.videoplayer.ad;end"
    links.append(f"• **MX Player:** `{mx_player_link}`")
    
    # VLC protocol
    vlc_link = f"vlc://{direct_url}"
    links.append(f"• **VLC Player:** `{vlc_link}`")
    
    # Direct URL (for any player)
    links.append(f"• **Direct URL:** `{direct_url}`")
    
    return "\n".join(links)

if __name__ == "__main__":
    print("🤖 Starting Telegram Wasabi Bot...")
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    app.run()
