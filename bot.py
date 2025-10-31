import logging
import requests
import time
from io import BytesIO
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import configuration
from config import config, validate_config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global statistics
upload_stats = {
    'total_uploads': 0,
    'successful_uploads': 0,
    'failed_uploads': 0,
    'start_time': time.time(),
    'status': 'online'
}

# Rate limiting
class RateLimiter:
    def __init__(self):
        self.user_uploads = defaultdict(list)
    
    def is_limited(self, user_id: int, max_uploads: int = 10, time_window: int = 3600) -> bool:
        now = time.time()
        self.user_uploads[user_id] = [ts for ts in self.user_uploads[user_id] 
                                    if now - ts < time_window]
        
        if len(self.user_uploads[user_id]) >= max_uploads:
            return True
        
        self.user_uploads[user_id].append(now)
        return False

rate_limiter = RateLimiter()

# --- HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and instructions on /start."""
    welcome_message = (
        "Hello! I'm your Image Uploader Bot. 📸\n\n"
        "Just send me an image (as a *photo*, not a document) and I will "
        "upload it to ImgBB and send you the direct URL.\n\n"
        f"🚨 *File Limit:* Images must be under {config.MAX_SIZE_MB}MB.\n"
        "⚡ *Rate Limit:* Max 10 uploads per hour per user."
    )
    await update.message.reply_text(
        welcome_message,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends help instructions."""
    help_message = (
        "How to use:\n"
        "1. Send a single image to this chat.\n"
        "2. Ensure the image is sent as a *Photo* (not compressed as a file).\n"
        f"3. The file size limit is {config.MAX_SIZE_MB}MB.\n"
        "4. Rate limit: 10 uploads per hour per user.\n"
        "I will reply with the ImgBB link upon successful upload."
    )
    await update.message.reply_text(help_message)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics."""
    uptime_seconds = time.time() - upload_stats['start_time']
    uptime_str = format_uptime(uptime_seconds)
    
    stats_message = (
        "📊 *Bot Statistics*\n\n"
        f"• Total Uploads: {upload_stats['total_uploads']}\n"
        f"• Successful: {upload_stats['successful_uploads']}\n"
        f"• Failed: {upload_stats['failed_uploads']}\n"
        f"• Success Rate: {calculate_success_rate()}%\n"
        f"• Uptime: {uptime_str}\n"
        f"• Status: 🟢 Online"
    )
    await update.message.reply_text(
        stats_message,
        parse_mode=constants.ParseMode.MARKDOWN
    )

def format_uptime(seconds: float) -> str:
    """Format uptime seconds to human readable string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def calculate_success_rate() -> float:
    """Calculate success rate percentage."""
    if upload_stats['total_uploads'] == 0:
        return 0.0
    return round((upload_stats['successful_uploads'] / upload_stats['total_uploads']) * 100, 1)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photo messages, checks size, and uploads to ImgBB."""
    user_id = update.effective_user.id
    message = update.message
    
    # Check rate limiting
    if rate_limiter.is_limited(user_id):
        await message.reply_text(
            "🚫 *Rate Limit Exceeded*\n\n"
            "You've reached the upload limit (10 images per hour). "
            "Please try again later.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return
    
    # Update total uploads count
    upload_stats['total_uploads'] += 1
    
    # 1. Get the largest photo available
    photo_file = message.photo[-1]
    chat_id = message.chat_id
    
    # Send initial loading message
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.UPLOAD_PHOTO)
    
    # 2. Get the file object to check size and download
    try:
        file = await context.bot.get_file(photo_file.file_id)
    except Exception as e:
        logger.error(f"Error retrieving file object: {e}")
        upload_stats['failed_uploads'] += 1
        await message.reply_text("❌ Error: Could not retrieve the file details from Telegram. Please try again.")
        return
    
    # 3. Check the file size limit
    if file.file_size > config.MAX_SIZE_BYTES:
        upload_stats['failed_uploads'] += 1
        await message.reply_text(
            f"🚫 *Error*: The image is too large ({file.file_size / (1024 * 1024):.2f}MB). "
            f"The limit is {config.MAX_SIZE_MB}MB.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await message.reply_text(f"📤 Uploading file ({file.file_size / (1024 * 1024):.2f}MB)... Please wait.")

    # 4. Download the file contents into memory
    file_bytes = BytesIO()
    try:
        await file.download_to_memory(file_bytes)
        file_bytes.seek(0)
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        upload_stats['failed_uploads'] += 1
        await message.reply_text("❌ Error: Could not download the image from Telegram servers.")
        return

    # 5. Prepare and send the image to ImgBB
    payload = {
        'key': config.IMGBB_API_KEY
    }
    
    files = {
        'image': ('image.jpg', file_bytes, 'image/jpeg')
    }

    try:
        # Perform the HTTP POST request to ImgBB
        imgbb_response = requests.post(config.IMGBB_UPLOAD_URL, data=payload, files=files)
        imgbb_response.raise_for_status()
        
        data = imgbb_response.json()

        # 6. Process ImgBB response
        if data.get('success') and data.get('data'):
            image_url = data['data']['url']
            delete_url = data['data']['delete_url']
            image_size = data['data']['size']
            
            # Update successful uploads
            upload_stats['successful_uploads'] += 1
            
            # Send the result back to the user
            success_message = (
                "✅ *Upload Successful!*\n\n"
                f"*Direct URL:* `{image_url}`\n"
                f"*Size:* {image_size}\n\n"
                f"🗑️ *Delete URL:* `{delete_url}`"
            )
            await message.reply_text(
                success_message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            upload_stats['failed_uploads'] += 1
            error_message = data.get('error', {}).get('message', 'Unknown upload error.')
            logger.error(f"ImgBB API error: {error_message}")
            await message.reply_text(f"❌ ImgBB Upload Failed: {error_message}")

    except requests.exceptions.HTTPError as http_err:
        upload_stats['failed_uploads'] += 1
        if http_err.response.status_code == 400:
            await message.reply_text("❌ ImgBB rejected the image. It might be corrupted or in an unsupported format.")
        elif http_err.response.status_code == 403:
            await message.reply_text("❌ ImgBB API key is invalid or expired.")
        else:
            await message.reply_text(f"❌ ImgBB server error (HTTP {http_err.response.status_code}).")
        logger.error(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        upload_stats['failed_uploads'] += 1
        logger.error(f"Request error occurred: {req_err}")
        await message.reply_text("❌ Upload Failed: Could not connect to the ImgBB server.")
    except Exception as e:
        upload_stats['failed_uploads'] += 1
        logger.error(f"An unexpected error occurred during upload: {e}")
        await message.reply_text("❌ An unexpected error occurred during the upload process.")

async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any non-photo messages."""
    await update.message.reply_text(
        "I only handle image uploads. Send me a *photo* to upload, or use /help for instructions.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

def get_bot_stats():
    """Get current bot statistics for the status server."""
    return {
        'status': 'online',
        'last_check': time.strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': format_uptime(time.time() - upload_stats['start_time']),
        'total_uploads': upload_stats['total_uploads'],
        'successful_uploads': upload_stats['successful_uploads'],
        'failed_uploads': upload_stats['failed_uploads'],
        'success_rate': calculate_success_rate()
    }

# --- MAIN FUNCTION ---

def main() -> None:
    """Start the bot."""
    # Validate configuration
    validate_config()
    
    # Create the Application and pass your bot's token.
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

    # Start the Bot
    logger.info("Starting bot...")
    logger.info(f"Bot started with file size limit: {config.MAX_SIZE_MB}MB")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except ValueError as e:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"Configuration Error: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
