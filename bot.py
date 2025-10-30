import os
import asyncio
import base64
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from config import config

# --- PYROGRAM CLIENT INITIALIZATION ---
app = Client(
    "file_store_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Filter to check if the user is an administrator
def admin_filter(_, __, m: Message):
    return m.from_user and m.from_user.id in config.ADMIN_IDS

admin_only = filters.create(admin_filter)

# --- BOT STARTUP HOOK ---
@app.on_startup()
async def startup():
    """Set bot username in config on startup"""
    me = await app.get_me()
    config.BOT_USERNAME = me.username
    print(f"Bot started as @{config.BOT_USERNAME}")

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handles the /start command with file ID parameter for direct downloads"""
    user_id = message.from_user.id
    args = message.command
    
    # Handle direct download links: /start file_<encoded_id>
    if len(args) > 1 and args[1].startswith('file_'):
        try:
            encoded_id = args[1].replace('file_', '')
            storage_id = int(base64.b64decode(encoded_id).decode())
            await handle_quick_download(client, message, storage_id)
            return
        except Exception as e:
            await message.reply_text("❌ Invalid or expired download link.")
            return
    
    if user_id in config.ADMIN_IDS:
        text = (
            "**Welcome to the File Store Bot!** 💾\n\n"
            "**Features:**\n"
            "• Upload files (Documents, Videos, Audio)\n"
            "• Generate instant download links\n"
            "• Quick shareable URLs\n"
            "• Admin-only access\n\n"
            "**Commands:**\n"
            "• Just send a file to upload\n"
            "• `/get <id>` - Download by ID\n"
            "• `/link <id>` - Generate shareable link\n"
            "• `/info <id>` - Get file info\n"
            "• `/stats` - Bot statistics\n\n"
            f"**Storage:** `{config.STORAGE_CHAT_ID}` | **Max Size:** {config.MAX_FILE_SIZE}MB"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Upload File", switch_inline_query="")],
            [InlineKeyboardButton("🆔 How to Use", callback_data="help")]
        ])
    else:
        text = (
            "🔒 **Private File Store Bot**\n\n"
            "This bot is for authorized administrators only.\n"
            "If you need access, contact the bot owner."
        )
        keyboard = None
        
    await message.reply_text(text, reply_markup=keyboard)

@app.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    await callback_query.answer()
    help_text = (
        "**Quick Guide:**\n\n"
        "1. **Upload**: Send any file (doc, video, audio)\n"
        "2. **Get ID**: You'll receive a storage ID\n"
        "3. **Download**: Use `/get ID` or generate a link with `/link ID`\n"
        "4. **Share**: Send the generated link to others\n\n"
        "**Example:**\n"
        "• Send a file → Get ID: 12345\n"
        "• Use `/link 12345` → Get shareable URL\n"
        "• Share URL → Anyone can download instantly"
    )
    await callback_query.message.edit_text(help_text)

async def handle_quick_download(client: Client, message: Message, storage_id: int):
    """Handle direct downloads from start links"""
    status_msg = await message.reply_text(f"⬇️ Downloading file...")
    
    try:
        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=config.STORAGE_CHAT_ID,
            message_id=storage_id
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Error downloading file: {str(e)}")

@app.on_message(filters.document | filters.video | filters.audio, group=1)
async def handle_file_upload(client: Client, message: Message):
    """Handles file uploads and provides multiple sharing options"""
    user_id = message.from_user.id
    if user_id not in config.ADMIN_IDS:
        await message.reply_text("🚫 Access Denied. Only administrators can upload files.")
        return

    # Check file size
    file_size = (
        (message.document and message.document.file_size) or
        (message.video and message.video.file_size) or
        (message.audio and message.audio.file_size) or
        0
    ) / (1024 * 1024)  # Convert to MB

    if file_size > config.MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ File too large! Maximum size is {config.MAX_FILE_SIZE} MB. "
            f"Your file is {file_size:.1f} MB."
        )
        return

    status_msg = await message.reply_text("🔄 Uploading to storage...")
    
    try:
        # Forward the file to storage
        stored_message = await client.forward_messages(
            chat_id=config.STORAGE_CHAT_ID,
            from_chat_id=message.chat.id,
            message_ids=message.id
        )

        storage_id = stored_message.id
        encoded_id = base64.b64encode(str(storage_id).encode()).decode()
        direct_link = f"https://t.me/{config.BOT_USERNAME}?start=file_{encoded_id}"

        # Get file info
        file_name = (
            (message.document and message.document.file_name) or
            (message.video and message.video.file_name) or
            (message.audio and message.audio.file_name) or
            "Unknown"
        )

        # Create share keyboard
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Copy Direct Link", url=f"tg://copy?text={quote(direct_link)}")],
            [
                InlineKeyboardButton("📥 Download Now", url=direct_link),
                InlineKeyboardButton("🆔 Get Command", callback_data=f"cmd_{storage_id}")
            ],
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={quote(direct_link)}")]
        ])

        await status_msg.edit_text(
            f"✅ **File Stored Successfully!**\n\n"
            f"**📁 File:** `{file_name}`\n"
            f"**💾 Size:** {file_size:.1f} MB\n"
            f"**🆔 Storage ID:** `{storage_id}`\n\n"
            f"**Quick Actions:**",
            reply_markup=keyboard
        )

    except FloodWait as e:
        await status_msg.edit_text(f"⏳ FloodWait: Try again in {e.value}s")
    except Exception as e:
        await status_msg.edit_text(f"❌ Storage error: {str(e)}")

@app.on_callback_query(filters.regex("^cmd_"))
async def get_command_callback(client, callback_query):
    """Show get command for the file"""
    storage_id = callback_query.data.replace("cmd_", "")
    command_text = f"/get {storage_id}"
    
    await callback_query.answer("Command copied to clipboard!", show_alert=False)
    
    # Edit message to show command
    await callback_query.message.edit_text(
        f"**Download Command:**\n\n`{command_text}`\n\n"
        f"Use this command in any chat with the bot to download the file.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Copy Command", url=f"tg://copy?text={command_text}")
        ]])
    )

@app.on_message(filters.command("get") & admin_only)
async def handle_file_download(client: Client, message: Message):
    """Handles file retrieval using /get <storage_id>"""
    if len(message.command) < 2:
        await message.reply_text("Usage: `/get <storage_id>`\nExample: `/get 12345`")
        return

    try:
        storage_id = int(message.command[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid storage ID. Must be a number.")
        return

    status_msg = await message.reply_text(f"⬇️ Fetching file ID `{storage_id}`...")

    try:
        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=config.STORAGE_CHAT_ID,
            message_id=storage_id
        )
        await status_msg.delete()
    except FloodWait as e:
        await status_msg.edit_text(f"⏳ FloodWait: Try again in {e.value}s")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: File not found or access denied.")

@app.on_message(filters.command("link") & admin_only)
async def generate_download_link(client: Client, message: Message):
    """Generate shareable download links"""
    if len(message.command) < 2:
        await message.reply_text("Usage: `/link <storage_id>`\nExample: `/link 12345`")
        return

    try:
        storage_id = int(message.command[1].strip())
        encoded_id = base64.b64encode(str(storage_id).encode()).decode()
        direct_link = f"https://t.me/{config.BOT_USERNAME}?start=file_{encoded_id}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Open Link", url=direct_link)],
            [InlineKeyboardButton("📋 Copy Link", url=f"tg://copy?text={direct_link}")],
            [InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={quote(direct_link)}")]
        ])
        
        await message.reply_text(
            f"**🔗 Shareable Download Link**\n\n"
            f"**Storage ID:** `{storage_id}`\n"
            f"**Direct Link:**\n`{direct_link}`\n\n"
            f"Anyone can click this link to download the file instantly!",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
    except ValueError:
        await message.reply_text("❌ Invalid storage ID. Must be a number.")
    except Exception as e:
        await message.reply_text(f"❌ Error generating link: {str(e)}")

@app.on_message(filters.command("info") & admin_only)
async def file_info(client: Client, message: Message):
    """Get information about a stored file"""
    if len(message.command) < 2:
        await message.reply_text("Usage: `/info <storage_id>`")
        return

    try:
        storage_id = int(message.command[1].strip())
        
        # Try to get the message from storage
        stored_msg = await client.get_messages(config.STORAGE_CHAT_ID, storage_id)
        
        if not stored_msg or not (stored_msg.document or stored_msg.video or stored_msg.audio):
            await message.reply_text("❌ File not found or invalid storage ID.")
            return

        # Extract file information
        file = stored_msg.document or stored_msg.video or stored_msg.audio
        file_name = getattr(file, 'file_name', 'Unknown')
        file_size = file.file_size / (1024 * 1024)  # MB
        mime_type = getattr(file, 'mime_type', 'Unknown')
        
        encoded_id = base64.b64encode(str(storage_id).encode()).decode()
        direct_link = f"https://t.me/{config.BOT_USERNAME}?start=file_{encoded_id}"
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Get Download Link", callback_data=f"link_{storage_id}")
        ]])
        
        info_text = (
            f"**📁 File Information**\n\n"
            f"**Name:** `{file_name}`\n"
            f"**Size:** {file_size:.2f} MB\n"
            f"**Type:** {mime_type}\n"
            f"**Storage ID:** `{storage_id}`\n"
            f"**Message Date:** {stored_msg.date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await message.reply_text(info_text, reply_markup=keyboard)
        
    except ValueError:
        await message.reply_text("❌ Invalid storage ID.")
    except Exception as e:
        await message.reply_text(f"❌ Error retrieving file info: {str(e)}")

@app.on_message(filters.command("stats") & admin_only)
async def bot_stats(client: Client, message: Message):
    """Show bot statistics"""
    try:
        bot_me = await client.get_me()
        stats_text = (
            f"**📊 Bot Statistics**\n\n"
            f"**🤖 Bot:** @{bot_me.username}\n"
            f"**👑 Admins:** {len(config.ADMIN_IDS)}\n"
            f"**💾 Storage:** `{config.STORAGE_CHAT_ID}`\n"
            f"**📦 Max File Size:** {config.MAX_FILE_SIZE} MB\n"
            f"**✅ Allowed Types:** {', '.join(config.ALLOWED_FILE_TYPES)}\n\n"
            f"**🔗 Features:**\n"
            f"• Direct download links\n"
            f"• Shareable URLs\n"
            f"• Instant file access\n"
            f"• Admin-only security"
        )
        await message.reply_text(stats_text)
    except Exception as e:
        await message.reply_text(f"❌ Error getting stats: {str(e)}")

# --- BOT STARTUP ---
if __name__ == "__main__":
    print("🚀 Starting Enhanced File Store Bot...")
    print(f"💾 Storage Chat: {config.STORAGE_CHAT_ID}")
    print(f"👑 Admins: {len(config.ADMIN_IDS)}")
    app.run()
