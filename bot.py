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

# --- HANDLERS (same as before) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and instructions on /start."""
    welcome_message = (
        "Hello! I'm your Image Uploader Bot. 📸\n\n"
        "Just send me an image (as a *photo*, not a document) and I will "
        "upload it to ImgBB and send you the direct URL.\n\n"
        f"🚨 *File Limit:* Images must be under {config.MAX_SIZE_MB}MB."
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
        "I will reply with the ImgBB link upon successful upload."
    )
    await update.message.reply_text(help_message)

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
    except Exception as e:
        logger.error(f"Error retrieving file object: {e}")
        await message.reply_text("❌ Error: Could not retrieve the file details from Telegram. Please try again.")
        return
    
    # 3. Check the file size limit
    if file.file_size > config.MAX_SIZE_BYTES:
        await message.reply_text(
            f"🚫 *Error*: The image is too large ({file.file_size / (1024 * 1024):.2f}MB). "
            f"The limit is {config.MAX_SIZE_MB}MB.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await message.reply_text(f"Uploading file ({file.file_size / (1024 * 1024):.2f}MB)... Please wait.")

    # 4. Download the file contents into memory
    file_bytes = BytesIO()
    try:
        await file.download_to_memory(file_bytes)
        file_bytes.seek(0)
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
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
            
            # Send the result back to the user
            success_message = (
                "✅ *Upload Successful!*\n\n"
                f"*Direct URL:* `{image_url}`\n\n"
                f"You can delete this image later using this link: `{delete_url}`"
            )
            await message.reply_text(
                success_message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            error_message = data.get('error', 'Unknown upload error.')
            logger.error(f"ImgBB API error: {error_message}")
            await message.reply_text(f"❌ ImgBB Upload Failed: {error_message}")

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        await message.reply_text(f"❌ Upload Failed due to HTTP Error: {http_err.response.status_code}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err}")
        await message.reply_text("❌ Upload Failed: Could not connect to the ImgBB server.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during upload: {e}")
        await message.reply_text("❌ An unexpected error occurred during the upload process.")

async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any non-photo messages."""
    await update.message.reply_text(
        "I only handle image uploads. Please send me a *photo* to upload."
    )

# --- WEBHOOK SETUP FOR PORT 8000 ---

async def set_webhook(application: Application, webhook_url: str) -> None:
    """Set up the webhook for the bot."""
    await application.bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True
    )
    logger.info(f"Webhook set to: {webhook_url}")

# --- MAIN FUNCTION WITH PORT 8000 ---

def main() -> None:
    """Start the bot with webhook on port 8000."""
    # Create the Application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

    # Webhook configuration
    WEBHOOK_URL = getattr(config, 'WEBHOOK_URL', None)
    PORT = getattr(config, 'PORT', 8000)
    
    if WEBHOOK_URL:
        # Webhook mode (for production)
        logger.info(f"Starting webhook on port {PORT}...")
        
        # Set up webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            secret_token=getattr(config, 'WEBHOOK_SECRET', None),
            drop_pending_updates=True
        )
    else:
        # Polling mode (for development)
        logger.info("Starting polling...")
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
