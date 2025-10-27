import telebot
import time
import logging
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

try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info("✅ Bot initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing TeleBot: {e}")
    exit()

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
            f"**Last Restart:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "**Commands:**\n"
            "/start - Show this message\n"
            "/status - Check bot status\n"
            "/ping - Test if bot is responsive\n\n"
            "**Note:** I automatically forward all messages from the source chat to destination chat."
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
            f"**Bot Username:** @{bot.get_me().username}\n"
            f"**Last Check:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "**Status:** ✅ **RUNNING**"
        )
        
        bot.reply_to(message, status_text, parse_mode='Markdown')
        logger.info(f"✅ Sent status to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in status handler: {e}")

@bot.message_handler(commands=['ping'])
def handle_ping(message):
    """Handle /ping command"""
    try:
        start_time = time.time()
        msg = bot.reply_to(message, "🏓 Pong!")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        bot.edit_message_text(
            f"🏓 **Pong!**\n⏱ Response time: `{response_time}ms`",
            chat_id=message.chat.id,
            message_id=msg.message_id,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Ping response: {response_time}ms")
        
    except Exception as e:
        logger.error(f"❌ Error in ping handler: {e}")

@bot.message_handler(commands=['restart'])
def handle_restart(message):
    """Handle /restart command (admin only)"""
    try:
        if ADMIN_USER_ID and str(message.from_user.id) == ADMIN_USER_ID:
            bot.reply_to(message, "🔄 Restarting bot...")
            logger.info("🔄 Bot restart initiated by admin")
            raise SystemExit
        else:
            bot.reply_to(message, "❌ Unauthorized. This command is for admins only.")
            logger.warning(f"❌ Unauthorized restart attempt by user {message.from_user.id}")
            
    except Exception as e:
        logger.error(f"❌ Error in restart handler: {e}")

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
    """
    Forward messages from source chat to destination chat
    """
    try:
        # Check if message is from the source chat
        if message.chat.id == SOURCE_CHAT_ID:
            # Forward the message
            bot.forward_message(
                chat_id=DESTINATION_CHAT_ID,
                from_chat_id=SOURCE_CHAT_ID,
                message_id=message.message_id
            )
            logger.info(f"✅ Forwarded message {message.message_id} from {SOURCE_CHAT_ID} to {DESTINATION_CHAT_ID}")
            
        # Optional: Log messages from other chats for debugging
        # else:
        #     logger.debug(f"📝 Ignored message from chat {message.chat.id} (not source chat)")
            
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"❌ Telegram API error while forwarding: {e}")
        if 'bot was blocked' in str(e).lower():
            logger.error("❌ Bot was blocked by the user")
        elif 'chat not found' in str(e).lower():
            logger.error("❌ Chat not found - check chat IDs")
        elif 'not enough rights' in str(e).lower():
            logger.error("❌ Bot doesn't have enough rights in the chat")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error in forward_messages: {e}")

# ==============================================================================
#                 --- ERROR HANDLING ---
# ==============================================================================

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Handle all other messages that don't match previous handlers"""
    if message.chat.type == 'private' and not message.text.startswith('/'):
        bot.reply_to(
            message, 
            "🤖 I'm a forwarding bot! I automatically forward messages from a specific source chat to a destination chat.\n\n"
            "Use /help to see available commands."
        )

# ==============================================================================
#                 --- MAIN EXECUTION LOOP ---
# ==============================================================================

def main():
    """Main function to start the bot"""
    # Validate configuration
    if BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        logger.error("❌ ERROR: Please set BOT_TOKEN in your .env file")
        return
        
    if SOURCE_CHAT_ID == -1001234567890 or DESTINATION_CHAT_ID == -1009876543210:
        logger.error("❌ ERROR: Please set SOURCE_CHAT_ID and DESTINATION_CHAT_ID in your .env file")
        return

    logger.info("=" * 60)
    logger.info("🚀 Starting Telegram Forwarder Bot")
    logger.info(f"📝 Source Chat: {SOURCE_CHAT_ID}")
    logger.info(f"📤 Destination Chat: {DESTINATION_CHAT_ID}")
    logger.info("⏰ Bot started at: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    try:
        # Test bot connection
        bot_info = bot.get_me()
        logger.info(f"✅ Bot connected successfully: @{bot_info.username} (ID: {bot_info.id})")
        
        # Start polling
        bot.infinity_polling(timeout=30, long_polling_timeout=10)
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"🚨 Fatal error in main loop: {e}")
        logger.info("🔄 Attempting to restart in 10 seconds...")
        time.sleep(10)
        main()  # Restart

if __name__ == '__main__':
    main()
