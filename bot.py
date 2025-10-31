import os
import re
import requests
import logging
import asyncio
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

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

# Thread pool for parallel API calls
executor = ThreadPoolExecutor(max_workers=5)

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

def shorten_link_api(service_key: str, long_url: str) -> dict:
    """
    Calls the external URL shortening API and returns result as dict.
    Returns: {'success': bool, 'service': str, 'url': str, 'error': str}
    """
    api_key = config.API_KEYS.get(service_key)
    api_url = config.SERVICE_ENDPOINTS.get(service_key)
    display_name = config.SERVICE_NAMES.get(service_key, service_key.upper())
    
    # Check if the API key is still the unconfigured placeholder
    if api_key in config.PLACEHOLDER_KEYS:
        return {
            'success': False,
            'service': display_name,
            'url': None,
            'error': "API Key not configured"
        }

    if not api_key or not api_url:
        return {
            'success': False,
            'service': display_name, 
            'url': None,
            'error': "Service configuration incomplete"
        }

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
                return {
                    'success': True,
                    'service': display_name,
                    'url': short_url,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'service': display_name,
                    'url': None,
                    'error': f"Invalid URL returned: {short_url}"
                }
        else:
            data = response.json()
            
            # Check for success and the shortened URL in the response
            if data.get('status') in ['success', 'ok'] and data.get(success_key):
                return {
                    'success': True,
                    'service': display_name,
                    'url': data[success_key],
                    'error': None
                }
            elif data.get(error_key):
                return {
                    'success': False,
                    'service': display_name,
                    'url': None,
                    'error': data[error_key]
                }
            else:
                return {
                    'success': False,
                    'service': display_name,
                    'url': None,
                    'error': "Could not parse short link from response"
                }

    except requests.exceptions.Timeout:
        logger.error(f"API Request timeout for {service_key}")
        return {
            'success': False,
            'service': display_name,
            'url': None,
            'error': "Service timeout"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed for {service_key}: {e}")
        return {
            'success': False,
            'service': display_name,
            'url': None,
            'error': f"Network error: {str(e)}"
        }
    except ValueError as e:
        logger.error(f"JSON parsing error for {service_key}: {e}")
        return {
            'success': False,
            'service': display_name,
            'url': None,
            'error': "Invalid response format"
        }
    except Exception as e:
        logger.error(f"Unexpected error during API call to {service_key}: {e}")
        return {
            'success': False,
            'service': display_name,
            'url': None,
            'error': f"Unexpected error: {str(e)}"
        }

async def shorten_all_services(long_url: str) -> list:
    """Shorten URL using all services in parallel"""
    services = ['gplinks', 'shrinkearn', 'shrtfly', 'fclc']
    
    # Run API calls in thread pool
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, shorten_link_api, service, long_url)
        for service in services
    ]
    
    # Wait for all results
    results = await asyncio.gather(*tasks)
    return results

def format_results_message(long_url: str, results: list) -> str:
    """Format the results into a nice message"""
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    message = f"🔗 **URL Shortening Results** 🔗\n\n"
    message += f"**Original URL:**\n`{long_url}`\n\n"
    message += f"**Results:** {success_count}/{total_count} successful\n\n"
    
    # Add successful results
    successful_services = [r for r in results if r['success']]
    if successful_services:
        message += "✅ **Shortened URLs:**\n"
        for result in successful_services:
            message += f"• **{result['service']}:** `{result['url']}`\n"
        message += "\n"
    
    # Add failed results
    failed_services = [r for r in results if not r['success']]
    if failed_services:
        message += "❌ **Failed Services:**\n"
        for result in failed_services:
            message += f"• **{result['service']}:** {result['error']}\n"
        message += "\n"
    
    message += "💡 *You can copy and share any of the successful links above.*"
    
    return message

# --- 5. TELEGRAM HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a welcome message and initiates the shortening conversation."""
    user = update.effective_user
    welcome_message = (
        f"👋 Welcome, {user.first_name}! I am your Mraprguild URL Shortener Bot.\n\n"
        "I can shorten links using four services: **GPLinks**, **ShrinkEarn**, **ShrtFly**, and **FC.LC**.\n\n"
        "**New Feature:** Now you can generate shortened URLs from **ALL services** at once!\n\n"
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
        "**✨ New Feature - All Services:**\n"
        "• Select 'All Services' to generate shortened URLs from ALL services at once\n"
        "• Get multiple links in one message\n"
        "• See which services worked and which failed\n\n"
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
    
    # Create the inline keyboard with service options including "All Services"
    keyboard = [
        [InlineKeyboardButton("🔗 GPLinks", callback_data='service_gplinks')],
        [InlineKeyboardButton("🔗 ShrinkEarn", callback_data='service_shrinkearn')],
        [InlineKeyboardButton("🔗 ShrtFly", callback_data='service_shrtfly')],
        [InlineKeyboardButton("🔗 FC.LC", callback_data='service_fclc')],
        [InlineKeyboardButton("🚀 ALL SERVICES", callback_data='service_all')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ URL received: `{normalized_url}`\n\n"
        "Now, please select the **shortening service** you want to use:\n\n"
        "💡 *Tip: Choose 'ALL SERVICES' to generate links from all services at once!*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return SELECT_SERVICE

async def process_single_service(service_data: str, long_url: str, query) -> int:
    """Process a single service selection"""
    display_name = config.SERVICE_NAMES.get(service_data, service_data.upper())

    # Update the message to show processing
    await query.edit_message_text(
        f"⏳ Shortening your link using **{display_name}**...\n\n"
        f"URL: `{long_url}`",
        parse_mode='Markdown'
    )

    # Call the API function
    result = shorten_link_api(service_data, long_url)

    # Prepare response based on result
    if result['success']:
        response_text = (
            f"✨ **Shortening Complete!** ✨\n\n"
            f"**Service:** {display_name}\n"
            f"**Original URL:** `{long_url}`\n"
            f"**Short Link:** `{result['url']}`\n\n"
            f"✅ You can copy and share the link above.\n"
            f"Use /shorten to shorten another link."
        )
    else:
        response_text = (
            f"❌ **Shortening Failed** ❌\n\n"
            f"**Service:** {display_name}\n"
            f"**Error Details:** {result['error']}\n\n"
            f"Please check your API key for {display_name} and try again, "
            f"or select a different service."
        )

    await query.edit_message_text(
        response_text,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

    return ConversationHandler.END

async def process_all_services(long_url: str, query) -> int:
    """Process all services in parallel"""
    # Update the message to show processing
    processing_message = await query.edit_message_text(
        f"🚀 **Generating URLs from ALL Services** 🚀\n\n"
        f"URL: `{long_url}`\n\n"
        f"⏳ Please wait while I contact all services...",
        parse_mode='Markdown'
    )

    # Get results from all services
    results = await shorten_all_services(long_url)
    
    # Format the results message
    response_text = format_results_message(long_url, results)
    
    # Send the results
    await query.edit_message_text(
        response_text,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

    return ConversationHandler.END

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

    if service_data == 'all':
        # Process all services
        return await process_all_services(long_url, query)
    else:
        # Process single service
        return await process_single_service(service_data, long_url, query)

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
        executor.shutdown()
        logger.info("Bot stopped")

if __name__ == "__main__":
    main()
