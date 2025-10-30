import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import config  # Import your config

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

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handles the /start command."""
    user_id = message.from_user.id
    
    if user_id in config.ADMIN_IDS:
        text = (
            "**Welcome to the File Store Bot (Admin Mode)!** 💾\n\n"
            "This bot uses Telegram as a high-speed file storage.\n\n"
            "**Upload/Store:** Simply send me a file (Document, Video, or Audio).\n"
            "**Retrieve/Download:** Use `/get <storage_id>` to fetch a file.\n\n"
            f"**Storage Chat ID:** `{config.STORAGE_CHAT_ID}`\n"
            f"**Allowed File Types:** {', '.join(config.ALLOWED_FILE_TYPES)}\n"
            f"**Max File Size:** {config.MAX_FILE_SIZE} MB"
        )
    else:
        text = (
            "Welcome! This is a private File Store Bot. "
            "Only designated administrators can upload and retrieve files."
        )
        
    await message.reply_text(text)

@app.on_message(filters.document | filters.video | filters.audio, group=1)
async def handle_file_upload(client: Client, message: Message):
    """Handles file uploads (Document, Video, Audio)."""
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

    status_msg = await message.reply_text("🔄 Processing file and uploading to store...")
    
    try:
        # Forward the file to storage
        stored_message = await client.forward_messages(
            chat_id=config.STORAGE_CHAT_ID,
            from_chat_id=message.chat.id,
            message_ids=message.id
        )

        storage_id = stored_message.id

        await status_msg.edit_text(
            f"✅ File stored successfully!\n\n"
            f"**Storage ID:** `{storage_id}`\n"
            f"**File Size:** {file_size:.1f} MB\n\n"
            "Use `/get {storage_id}` to retrieve it."
        )

    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Telegram FloodWait: Try again in {e.value} seconds.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error during storage: {str(e)}")

@app.on_message(filters.command("get") & admin_only)
async def handle_file_download(client: Client, message: Message):
    """Handles file retrieval using /get <storage_id>."""
    if len(message.command) < 2:
        await message.reply_text("Usage: `/get <storage_id>` (e.g., /get 12345)")
        return

    try:
        storage_id = int(message.command[1].strip())
    except ValueError:
        await message.reply_text("Invalid storage ID. It must be a number.")
        return

    status_msg = await message.reply_text(f"⬇️ Fetching file with ID `{storage_id}`...")

    try:
        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=config.STORAGE_CHAT_ID,
            message_id=storage_id
        )
        await status_msg.delete()

    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Telegram FloodWait: Try again in {e.value} seconds.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error fetching file ID `{storage_id}`: {str(e)}")

# --- BOT STARTUP ---
if __name__ == "__main__":
    print("Starting Telegram File Store Bot...")
    print(f"Admin IDs: {config.ADMIN_IDS}")
    print(f"Storage Chat ID: {config.STORAGE_CHAT_ID}")
    app.run()
