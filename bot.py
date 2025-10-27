import telebot
import time
import logging
from datetime import datetime

# Import configuration
from config import config

# ==============================================================================
#                 --- INITIALIZATION ---
# ==============================================================================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    bot = telebot.TeleBot(config.BOT_TOKEN)
except Exception as e:
    logger.error(f"Error initializing TeleBot: {e}")
    exit()

# ==============================================================================
#                 --- HANDLERS AND LOGIC ---
# ==============================================================================

@bot.message_handler(content_types=config.FORWARD_CONTENT_TYPES)
def forward_messages(message):
    """
    Listens for messages and forwards them if from the source chat.
    """
    if message.chat.id == config.SOURCE_CHAT_ID:
        try:
            bot.forward_message(
                chat_id=config.DESTINATION_CHAT_ID,
                from_chat_id=config.SOURCE_CHAT_ID,
                message_id=message.message_id
            )
            logger.info(f"✅ Forwarded message ID {message.message_id}")

        except telebot.apihelper.ApiTelegramException as e:
            error_msg = f"❌ API Error: {e}"
            logger.error(error_msg)
            
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")

@bot.message_handler(commands=['start', 'help', 'status'])
def send_welcome(message):
    """Responds to commands with bot status."""
    welcome_text = (
        "🤖 Telegram Forwarder Bot Status 🤖\n\n"
        f"Source: `{config.SOURCE_CHAT_ID}`\n"
        f"Destination: `{config.DESTINATION_CHAT_ID}`\n"
        f"Last restart: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "Ensure I'm an **administrator** in both chats."
    )
    
    # Only respond in private or destination chat
    if message.chat.type == 'private' or message.chat.id == config.DESTINATION_CHAT_ID:
        try:
            bot.reply_to(message, welcome_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

@bot.message_handler(commands=['restart'])
def restart_bot(message):
    """Admin-only restart command (optional)"""
    if (config.ADMIN_USER_ID and 
        str(message.from_user.id) == config.ADMIN_USER_ID):
        bot.reply_to(message, "🔄 Restarting bot...")
        logger.info("Bot restart initiated by admin")
        raise SystemExit  # This will trigger the restart in main()
    else:
        bot.reply_to(message, "❌ Unauthorized.")

# ==============================================================================
#                 --- MAIN EXECUTION LOOP ---
# ==============================================================================

def main():
    """Main function to start the bot."""
    logger.info("=========================================================")
    logger.info("🚀 Forwarder Bot starting...")
    logger.info(f"Source: {config.SOURCE_CHAT_ID} | Destination: {config.DESTINATION_CHAT_ID}")
    logger.info("Press Ctrl+C to stop the bot.")
    logger.info("=========================================================")
    
    # Validate configuration
    if (config.BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE' or 
        config.SOURCE_CHAT_ID == -1001234567890 or 
        config.DESTINATION_CHAT_ID == -1009876543210):
        logger.error("ERROR: Please update the configuration in config.py or .env file")
        return
    
    try:
        bot.infinity_polling(
            timeout=config.POLLING_TIMEOUT,
            long_polling_timeout=config.LONG_POLLING_TIMEOUT
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"🚨 Fatal error: {e}")
        time.sleep(5)
        main()  # Restart

if __name__ == '__main__':
    main()
