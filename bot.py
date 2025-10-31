import os
import re
import requests
import logging
from urllib.parse import urlparse

# --- 1. CONFIGURATION: IMPORT SETTINGS ---
from config import config

# --- 2. BOT SETUP AND LOGGING ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Conversation states
GET_URL, SELECT_SERVICE = range(2)

# --- 3. UTILITY FUNCTIONS ---

def is_valid_url(url: str) -> bool:
    """Enhanced URL validation with regex"""
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(pattern, url) is not None

def normalize_url(url: str) -> str:
    """Normalize URL by adding scheme if missing"""
    if not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url

# --- 4. API INTEGRATION FUNCTIONS ---

def shorten_link_api(service_key: str, long_url: str) -> str:
    """
    Calls the external URL shortening API and returns the short link or an error message.
    """
    api_key = config.API_KEYS.get(service_key)
    api_url = config.SERVICE_ENDPOINTS.get(service_key)
    
    # Check if the API key is still the unconfigured placeholder
    if api_key in config.PLACEHOLDER_KEYS:
        return "⚠️ API Key not configured for this service in config.py. Please update it."

    if not api_key or not api_url:
        return f"⚠️ Error: Service configuration for '{service_key}' is incomplete."

    # Service-specific API parameters
    service_configs = {
        'gplinks': {
            'params': {'api': api_key, 'url': long_url, 'format': 'json'},
            'success_key': 'shortenedUrl',
            'error_key': 'message'
        },
        'shrinkearn': {
            'params': {'api': api_key, 'url': long_url},
            'success_key': 'shortenedUrl',
            'error_key': 'error'
        },
        'shrtfly': {
            'params': {'api': api_key, 'url': long_url, 'format': 'text'},
            'success_key': 'shortenedUrl', 
            'error_key': 'message'
        },
        'fclc': {
            'params': {'api': api_key, 'url': long_url},
            'success_key': 'shortenedUrl',
            'error_key': 'error'
        }
    }
    
    config_data = service_configs.get(service_key, {})
    params = config_data.get('params', {})
    success_key = config_data.get('success_key', 'shortenedUrl')
    error_key = config_data.get('error_key', 'message')
    
    try:
        # Use a timeout to prevent the bot from hanging
        response = requests.get(api_url, params=params, timeout=15)
        response.raise_for_status()
        
        # Handle different response formats
        if params.get('format') == 'text':
            short_url = response.text.strip()
            if short_url and short_url.startswith('http'):
                return short_url
            else:
                return f"❌ API returned invalid URL: {short_url}"
        else:
            data = response.json()
            
            # Check for success and the shortened URL in the response
            if data.get('status') in ['success', 'ok'] and data.get(success_key):
                return data[success_key]
            elif data.get(error_key):
                return f"❌ API Error: {data[error_key]}"
            else:
                return "❌ API Response Error: Could not parse the short link from the service."

    except requests.exceptions.Timeout:
        logger.error(f"API Request timeout for {service_key}")
        return f"❌ Timeout Error: {service_key.upper()} service is taking too long to respond."
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed for {service_key}: {e}")
        return f"❌ Network Error: Could not connect to {service_key.upper()}. Try again later."
    except ValueError as e:
        logger.error(f"JSON parsing error for {service_key}: {e}")
        return f"❌ API Response Error: Invalid response format from {service_key.upper()}."
    except Exception as e:
        logger.error(f"Unexpected error during API call to {service_key}: {e}")
        return "❌ An unexpected error occurred."

# --- 5. TELEGRAM HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a welcome message and initiates the shortening conversation."""
    user = update.effective_user
    welcome_message = (
        f"👋 Welcome, {user.first_name}! I am your Mraprguild URL Shortener Bot.\n\n"
        "I can shorten links using four services: **GPLinks**, **ShrinkEarn**, **ShrtFly**, and **FC.LC**.\n\n"
        "To begin, type /shorten or click the button below.\n\n"
        "Available commands:\n"
        "• /start - Start the bot\n"
        "• /shorten - Shorten a new URL\n" 
        "• /help - Show help information\n"
        "• /cancel - Cancel current operation"
    )
    
    keyboard = [[InlineKeyboardButton("🔗 Shorten URL", callback_data="start_shorten")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    help_text = (
        "🤖 **URL Shortener Bot Help**\n\n"
        "**How to use:**\n"
        "1. Use /shorten to start\n"
        "2. Send me the long URL you want to shorten\n"
        "3. Choose your preferred shortening service\n"
        "4. Get your shortened link!\n\n"
        "**Supported Services:**\n"
        "• GPLinks (gplinks.in)\n"
        "• ShrinkEarn (shrinkearn.com)\n" 
        "• ShrtFly (shrtfly.com)\n"
        "• FC.LC (fc.lc)\n\n"
        "**Notes:**\n"
        "• URLs must start with http:// or https://\n"
        "• Some services may require authentication\n"
        "• Use /cancel anytime to stop current operation"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and prompts the user for the URL."""
    # Clear any previous user data
    context.user_data.clear()
    
    await update.message.reply_text(
        "🔗 Please send me the **long URL** you wish to shorten.\n\n"
        "Example: `https://example.com/very/long/url/path`",
        parse_mode='Markdown'
    )
    return GET_URL

async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the URL from the user and presents the service options."""
    long_url = update.message.text.strip()
    
    # Normalize URL (add https:// if missing)
    normalized_url = normalize_url(long_url)
    
    # Enhanced URL validation
    if not is_valid_url(normalized_url):
        await update.message.reply_text(
            "❌ That doesn't look like a valid URL. Please send a valid URL starting with `http://` or `https://`.\n\n"
            "Example: `https://example.com`",
            parse_mode='Markdown'
        )
        return GET_URL

    # Store the normalized URL in user data
    context.user_data['long_url'] = normalized_url
    
    # Create the inline keyboard with service options
    keyboard = [
        [InlineKeyboardButton("🔗 GPLinks", callback_data='service_gplinks')],
        [InlineKeyboardButton("🔗 ShrinkEarn", callback_data='service_shrinkearn')],
        [InlineKeyboardButton("🔗 ShrtFly", callback_data='service_shrtfly')],
        [InlineKeyboardButton("🔗 FC.LC", callback_data='service_fclc')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ URL received: `{normalized_url}`\n\n"
        "Now, please select the **shortening service** you want to use:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return SELECT_SERVICE

async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's service selection via inline keyboard."""
    query = update.callback_query
    await query.answer()

    service_data = query.data.replace('service_', '')
    long_url = context.user_data.get('long_url')
    
    if not long_url:
        await query.edit_message_text(
            "❌ Error: I lost the original URL. Please start again with /shorten."
        )
        return ConversationHandler.END

    # Get the service name for display
    service_names = {
        'gplinks': 'GPLinks', 
        'shrinkearn': 'ShrinkEarn', 
        'shrtfly': 'ShrtFly', 
        'fclc': 'FC.LC'
    }
    display_name = service_names.get(service_data, service_data.upper())

    # Update the message to show processing
    processing_message = await query.edit_message_text(
        f"⏳ Shortening your link using **{display_name}**...\n\n"
        f"URL: `{long_url}`",
        parse_mode='Markdown'
    )

    # Call the API function
    short_link = shorten_link_api(service_data, long_url)

    # Prepare response based on result
    if short_link.startswith("http"):
        # Success case
        response_text = (
            f"✨ **Shortening Complete!** ✨\n\n"
            f"**Service:** {display_name}\n"
            f"**Original URL:** `{long_url}`\n"
            f"**Short Link:** `{short_link}`\n\n"
            f"✅ You can copy and share the link above.\n"
            f"Use /shorten to shorten another link."
        )
    else:
        # Error case
        response_text = (
            f"❌ **Shortening Failed** ❌\n\n"
            f"**Service:** {display_name}\n"
            f"**Error Details:** {short_link}\n\n"
            f"Please check your API key for {display_name} and try again, "
            f"or select a different service."
        )

    await query.edit_message_text(
        response_text,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        '❌ Operation cancelled. Use /shorten to start a new one.'
    )
    return ConversationHandler.END

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback handler for text messages not during the conversation flow."""
    await update.message.reply_text(
        "🤖 I'm designed to shorten links. Use the /shorten command to start the process "
        "or /help for more information."
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_shorten":
        return await shorten_command(update, context)

# --- 6. MAIN EXECUTION ---

def main() -> None:
    """Start the bot."""
    # Check for the main Telegram bot token
    if config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("🚨 FATAL: Please set TELEGRAM_BOT_TOKEN environment variable or update config.py")
        return

    # Create the Application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))
    
    # The conversation handler manages the state flow
    shorten_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("shorten", shorten_command),
            CallbackQueryHandler(button_handler, pattern="^start_shorten$")
        ],
        
        states={
            GET_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)
            ],
            SELECT_SERVICE: [
                CallbackQueryHandler(select_service, pattern='^service_'),
                CommandHandler('cancel', cancel)
            ],
        },
        
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(shorten_conv_handler)
    
    # Add a catch-all handler for text messages outside the conversation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler))
    
    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^start_shorten$"))

    # Run the bot
    logger.info("Bot is starting...")
    print("🤖 URL Shortener Bot is running! Press Ctrl+C to stop.")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    main()
