import logging
import requests
from io import BytesIO
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import configuration
from config import config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and instructions on /start."""
    welcome_message = (
        "🤖 *Image Uploader Bot*\n\n"
        "Send me an image as a *photo* (not a document) and I'll upload it to ImgBB "
        "and send you the direct URL.\n\n"
        f"📁 *File Limit:* Under {config.MAX_SIZE_MB}MB\n"
        "⚡ *Supported:* JPEG, PNG, GIF\n\n"
        "Use /help for more instructions."
    )
    await update.message.reply_text(
        welcome_message,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends help instructions."""
    help_message = (
        "📖 *How to use this bot:*\n\n"
        "1. 📸 Send a single image to this chat\n"
        "2. 🖼️ Make sure it's sent as a *Photo* (not as a file)\n"
        f"3. 📊 File size limit: {config.MAX_SIZE_MB}MB\n"
        "4. ⏳ Wait for the upload to complete\n\n"
        "I'll reply with the ImgBB direct URL and delete link."
    )
    await update.message.reply_text(help_message)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows bot status."""
    mode = "🌐 Webhook" if config.WEBHOOK_URL else "🔍 Polling"
    status_message = (
        f"🤖 *Bot Status*\n\n"
        f"*Mode:* {mode}\n"
        f"*Max File Size:* {config.MAX_SIZE_MB}MB\n"
        f"*Port:* {config.PORT}\n"
        f"*Status:* ✅ Operational"
    )
    await update.message.reply_text(status_message)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photo messages, checks size, and uploads to ImgBB."""
    message = update.message
    
    # 1. Get the largest photo available
    photo_file = message.photo[-1]
    chat_id = message.chat_id
    
    # Send initial loading message
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.UPLOAD_PHOTO)
    
    # 2. Get the file object to check size and download
    try:
        file = await context.bot.get_file(photo_file.file_id)
        logger.info(f"Processing photo: {file.file_id}, size: {file.file_size} bytes")
    except Exception as e:
        logger.error(f"Error retrieving file object: {e}")
        await message.reply_text("❌ Error: Could not retrieve the file details from Telegram. Please try again.")
        return
    
    # 3. Check the file size limit
    if file.file_size > config.MAX_SIZE_BYTES:
        size_mb = file.file_size / (1024 * 1024)
        await message.reply_text(
            f"🚫 *Error*: The image is too large ({size_mb:.2f}MB). "
            f"The limit is {config.MAX_SIZE_MB}MB.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    # 4. Show upload progress
    progress_msg = await message.reply_text(
        f"📤 Uploading image ({file.file_size / (1024 * 1024):.2f}MB)... Please wait."
    )

    # 5. Download the file contents into memory
    file_bytes = BytesIO()
    try:
        await file.download_to_memory(file_bytes)
        file_bytes.seek(0)
        logger.info(f"Downloaded photo successfully, size: {len(file_bytes.getvalue())} bytes")
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        await progress_msg.edit_text("❌ Error: Could not download the image from Telegram servers.")
        return

    # 6. Prepare and send the image to ImgBB
    payload = {
        'key': config.IMGBB_API_KEY
    }
    
    files = {
        'image': ('image.jpg', file_bytes, 'image/jpeg')
    }

    try:
        # Update progress
        await progress_msg.edit_text("🔄 Uploading to ImgBB...")
        
        # Perform the HTTP POST request to ImgBB
        imgbb_response = requests.post(config.IMGBB_UPLOAD_URL, data=payload, files=files, timeout=30)
        imgbb_response.raise_for_status()
        
        data = imgbb_response.json()
        logger.info(f"ImgBB response: {data.get('status')}")

        # 7. Process ImgBB response
        if data.get('success') and data.get('data'):
            image_data = data['data']
            image_url = image_data['url']
            delete_url = image_data['delete_url']
            image_title = image_data.get('title', 'Uploaded Image')
            
            # Send the result back to the user
            success_message = (
                "✅ *Upload Successful!*\n\n"
                f"*Title:* {image_title}\n"
                f"*Direct URL:* `{image_url}`\n"
                f"*View URL:* {image_data['display_url']}\n\n"
                f"🗑️ *Delete Link:* `{delete_url}`"
            )
            await progress_msg.edit_text(
                success_message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            error_message = data.get('error', {}).get('message', 'Unknown upload error.')
            logger.error(f"ImgBB API error: {error_message}")
            await progress_msg.edit_text(f"❌ ImgBB Upload Failed: {error_message}")

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        await progress_msg.edit_text(f"❌ Upload Failed: HTTP Error {http_err.response.status_code}")
    except requests.exceptions.Timeout:
        logger.error("ImgBB request timed out")
        await progress_msg.edit_text("❌ Upload Failed: Request timed out. Please try again.")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err}")
        await progress_msg.edit_text("❌ Upload Failed: Could not connect to the ImgBB server.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during upload: {e}")
        await progress_msg.edit_text("❌ An unexpected error occurred during the upload process.")

async def handle_document_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles images sent as documents."""
    await update.message.reply_text(
        "📎 Please send the image as a *Photo* (not as a document) for automatic upload.\n\n"
        "Tip: When sending an image, use the 'Photo' option instead of 'Document'.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any non-photo messages."""
    await update.message.reply_text(
        "🤖 I only handle image uploads. Send me a *photo* to upload to ImgBB.\n\n"
        "Use /help for instructions or /status to check bot status.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles errors in the telegram bot."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    # Notify user about the error
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again."
        )

# --- WEBHOOK SETUP ---

async def setup_webhook(application: Application):
    """Set up the webhook if configured."""
    if config.WEBHOOK_URL:
        webhook_url = f"{config.WEBHOOK_URL}"
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=config.WEBHOOK_SECRET,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to: {webhook_url}")

# --- MAIN FUNCTION ---

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE & ~filters.COMMAND, handle_document_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))
    
    # Register error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    if config.WEBHOOK_URL:
        # Webhook mode (production)
        logger.info(f"🚀 Starting webhook server on {config.LISTEN_ADDRESS}:{config.PORT}")
        logger.info(f"🌐 Webhook URL: {config.WEBHOOK_URL}")
        
        try:
            application.run_webhook(
                listen=config.LISTEN_ADDRESS,
                port=config.PORT,
                webhook_url=config.WEBHOOK_URL,
                secret_token=config.WEBHOOK_SECRET,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Webhook startup failed: {e}")
            logger.info("Falling back to polling mode...")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        # Polling mode (development)
        logger.info("🔍 Starting in polling mode...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
