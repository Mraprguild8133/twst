import telebot
import time
import logging
import sys
import signal
from datetime import datetime
from config import BOT_TOKEN, SOURCE_CHAT_ID, DESTINATION_CHAT_ID, ADMIN_USER_ID

# ==============================================================================
#                 --- INITIALIZATION ---
# ==============================================================================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variable to control bot running state
bot_running = True

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global bot_running
    logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    bot_running = False
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info("✅ Bot initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing TeleBot: {e}")
    sys.exit(1)

# ==============================================================================
#                 --- COMMAND HANDLERS ---
# ==============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """Handle /start and /help commands"""
    try:
        welcome_text = (
            "🤖 **Telegram Forwarder Bot** 🤖\n\n"
            "**Status:** ✅ Active\n"
            f"**Source Chat:** `{SOURCE_CHAT_ID}`\n"
            f"**Destination Chat:** `{DESTINATION_CHAT_ID}`\n"
            f"**Bot Username:** @{bot.get_me().username}\n\n"
            "**Commands:**\n"
            "/start - Show this message\n"
            "/status - Check bot status\n"
            "/stop - Stop the bot (admin only)\n\n"
            "I automatically forward messages from source to destination."
        )
        
        bot.reply_to(message, welcome_text, parse_mode='Markdown')
        logger.info(f"✅ Sent welcome message to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in start/help handler: {e}")

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Handle /status command"""
    try:
        status_text = (
            "📊 **Bot Status** 📊\n\n"
            f"**Source:** `{SOURCE_CHAT_ID}`\n"
            f"**Destination:** `{DESTINATION_CHAT_ID}`\n"
            f"**Bot ID:** `{bot.get_me().id}`\n"
            f"**Status:** ✅ **RUNNING**\n"
            f"**Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        bot.reply_to(message, status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in status handler: {e}")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    """Handle /stop command (admin only)"""
    try:
        if ADMIN_USER_ID and str(message.from_user.id) == ADMIN_USER_ID:
            bot.reply_to(message, "🛑 Stopping bot...")
            logger.info("🛑 Bot stop initiated by admin")
            global bot_running
            bot_running = False
            sys.exit(0)
        else:
            bot.reply_to(message, "❌ Unauthorized. This command is for admins only.")
            
    except Exception as e:
        logger.error(f"❌ Error in stop handler: {e}")

# ==============================================================================
#                 --- MESSAGE FORWARDING LOGIC ---
# ==============================================================================

@bot.message_handler(
    content_types=[
        'text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker',
        'animation', 'poll', 'location', 'contact', 'dice', 'video_note'
    ]
)
def forward_messages(message):
    """Forward messages from source chat to destination chat"""
    try:
        if message.chat.id == SOURCE_CHAT_ID:
            bot.forward_message(
                chat_id=DESTINATION_CHAT_ID,
                from_chat_id=SOURCE_CHAT_ID,
                message_id=message.message_id
            )
            logger.info(f"✅ Forwarded message {message.message_id}")
            
    except Exception as e:
        logger.error(f"❌ Error forwarding message: {e}")

# ==============================================================================
#                 --- IMPROVED POLLING WITH CONFLICT HANDLING ---
# ==============================================================================

def start_bot():
    """Start the bot with proper conflict handling"""
    # Validate configuration
    if BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        logger.error("❌ ERROR: Please set BOT_TOKEN in your .env file")
        return
        
    if SOURCE_CHAT_ID == -1001234567890 or DESTINATION_CHAT_ID == -1009876543210:
        logger.error("❌ ERROR: Please set SOURCE_CHAT_ID and DESTINATION_CHAT_ID")
        return

    logger.info("=" * 60)
    logger.info("🚀 Starting Telegram Forwarder Bot")
    logger.info(f"📝 Source: {SOURCE_CHAT_ID}")
    logger.info(f"📤 Destination: {DESTINATION_CHAT_ID}")
    logger.info("⏰ " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    try:
        # Test bot connection
        bot_info = bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Clear any existing webhook to avoid conflicts
        bot.remove_webhook()
        time.sleep(0.5)
        
        # Start polling with error handling
        logger.info("🔄 Starting polling...")
        bot.infinity_polling(
            timeout=30, 
            long_polling_timeout=10,
            logger_level=logging.ERROR
        )
        
    except telebot.apihelper.ApiException as e:
        if "Conflict" in str(e) or "409" in str(e):
            logger.error("🚨 CONFLICT: Another bot instance is running!")
            logger.error("💡 Solution: Kill other instances with: pkill -f python")
            time.sleep(5)
            # Don't auto-restart on conflict
        else:
            logger.error(f"🚨 Telegram API error: {e}")
            logger.info("🔄 Restarting in 10 seconds...")
            time.sleep(10)
            start_bot()
            
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"🚨 Unexpected error: {e}")
        logger.info("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
