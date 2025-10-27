import telebot
import time
import logging
import sys
import signal
import threading
import traceback
from datetime import datetime
from flask import Flask, jsonify
from config import BOT_TOKEN, SOURCE_CHAT_ID, DESTINATION_CHAT_ID, ADMIN_USER_ID

# ==============================================================================
#                 --- INITIALIZATION ---
# ==============================================================================

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

# Initialize bot with error handling
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info("✅ Bot object created successfully")
except Exception as e:
    logger.error(f"❌ Error initializing TeleBot: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)

# ==============================================================================
#                 --- HEALTH CHECK SERVER (PORT 8000) ---
# ==============================================================================

def create_health_server():
    """Create a simple health check server on port 8000"""
    try:
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return """
            <html>
                <head>
                    <title>Telegram Forwarder Bot</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; }
                        .status { color: green; font-weight: bold; }
                        .container { max-width: 800px; margin: 0 auto; }
                        .error { color: red; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 Telegram Forwarder Bot</h1>
                        <p class="status">Status: ✅ RUNNING</p>
                        <p><strong>Source Chat:</strong> {}</p>
                        <p><strong>Destination Chat:</strong> {}</p>
                        <p><strong>Start Time:</strong> {}</p>
                        <br>
                        <p><a href="/health">Health Check</a> | <a href="/status">Status API</a> | <a href="/metrics">Metrics</a></p>
                    </div>
                </body>
            </html>
            """.format(SOURCE_CHAT_ID, DESTINATION_CHAT_ID, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        @app.route('/health')
        def health():
            """Health check endpoint"""
            try:
                # Test bot connection
                bot.get_me()
                return jsonify({
                    "status": "healthy",
                    "service": "telegram-forwarder-bot",
                    "timestamp": datetime.now().isoformat(),
                    "bot_connected": True
                })
            except Exception as e:
                return jsonify({
                    "status": "unhealthy",
                    "service": "telegram-forwarder-bot",
                    "error": str(e),
                    "bot_connected": False
                }), 500
        
        @app.route('/status')
        def status():
            """Status endpoint with bot information"""
            try:
                bot_info = bot.get_me()
                return jsonify({
                    "status": "running",
                    "bot_username": f"@{bot_info.username}",
                    "bot_id": bot_info.id,
                    "source_chat": SOURCE_CHAT_ID,
                    "destination_chat": DESTINATION_CHAT_ID,
                    "timestamp": datetime.now().isoformat(),
                    "health": "ok"
                })
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }), 500
        
        @app.route('/metrics')
        def metrics():
            """Simple metrics endpoint"""
            return jsonify({
                "service": "telegram_bot",
                "active": True,
                "timestamp": datetime.now().isoformat()
            })
        
        # Run Flask server
        logger.info("🌐 Starting health check server on port 8000...")
        app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
        
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")
        logger.error(traceback.format_exc())

# Start health server in a separate thread (only if not already running)
try:
    health_thread = threading.Thread(target=create_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ Health server thread started")
except Exception as e:
    logger.error(f"❌ Failed to start health server: {e}")

# ==============================================================================
#                 --- COMMAND HANDLERS ---
# ==============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """Handle /start and /help commands"""
    try:
        bot_info = bot.get_me()
        welcome_text = (
            "🤖 **Telegram Forwarder Bot** 🤖\n\n"
            "**Status:** ✅ Active\n"
            f"**Source Chat:** `{SOURCE_CHAT_ID}`\n"
            f"**Destination Chat:** `{DESTINATION_CHAT_ID}`\n"
            f"**Bot Username:** @{bot_info.username}\n\n"
            "**Commands:**\n"
            "/start - Show this message\n"
            "/status - Check bot status\n"
            "/health - Health check\n"
            "/stop - Stop the bot (admin only)\n\n"
            "I automatically forward messages from source to destination."
        )
        
        bot.reply_to(message, welcome_text, parse_mode='Markdown')
        logger.info(f"✅ Sent welcome message to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in start/help handler: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Handle /status command"""
    try:
        bot_info = bot.get_me()
        status_text = (
            "📊 **Bot Status** 📊\n\n"
            f"**Bot:** @{bot_info.username} (ID: {bot_info.id})\n"
            f"**Source:** `{SOURCE_CHAT_ID}`\n"
            f"**Destination:** `{DESTINATION_CHAT_ID}`\n"
            f"**Status:** ✅ **RUNNING**\n"
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "**Health Check:** http://localhost:8000/health"
        )
        
        bot.reply_to(message, status_text, parse_mode='Markdown')
        logger.info(f"✅ Sent status to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in status handler: {e}")
        logger.error(traceback.format_exc())
        bot.reply_to(message, "❌ Error getting bot status")

@bot.message_handler(commands=['health'])
def handle_health(message):
    """Handle /health command"""
    try:
        # Test bot connection
        bot_info = bot.get_me()
        health_text = (
            "❤️ **Health Status** ❤️\n\n"
            "✅ **Bot:** Running\n"
            "✅ **API:** Connected\n"
            "✅ **Forwarding:** Active\n"
            f"🤖 **Bot:** @{bot_info.username}\n"
            f"⏰ **Last Check:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            "All systems operational! 🚀"
        )
        
        bot.reply_to(message, health_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in health handler: {e}")
        bot.reply_to(message, "❌ Health check failed - bot not connected")

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
            logger.warning(f"❌ Unauthorized stop attempt by user {message.from_user.id}")
            
    except Exception as e:
        logger.error(f"❌ Error in stop handler: {e}")
        logger.error(traceback.format_exc())

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
            logger.info(f"📨 Received message {message.message_id} from source chat")
            
            bot.forward_message(
                chat_id=DESTINATION_CHAT_ID,
                from_chat_id=SOURCE_CHAT_ID,
                message_id=message.message_id
            )
            
            logger.info(f"✅ Forwarded message {message.message_id} from {SOURCE_CHAT_ID} to {DESTINATION_CHAT_ID}")
            
    except telebot.apihelper.ApiTelegramException as e:
        error_msg = f"❌ Telegram API error forwarding message {message.message_id}: {e}"
        logger.error(error_msg)
        
        # Specific error handling
        if "bot was blocked" in str(e):
            logger.error("💡 The bot was blocked by a user")
        elif "chat not found" in str(e):
            logger.error("💡 Chat not found - check if bot was added to the chat")
        elif "not enough rights" in str(e):
            logger.error("💡 Bot doesn't have permission to forward messages")
        elif "message to forward not found" in str(e):
            logger.error("💡 Message was deleted or not accessible")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error forwarding message {message.message_id}: {e}")
        logger.error(traceback.format_exc())

# ==============================================================================
#                 --- ERROR HANDLER FOR OTHER MESSAGES ---
# ==============================================================================

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Handle all other messages that don't match previous handlers"""
    try:
        if message.chat.type == 'private' and not message.text.startswith('/'):
            bot.reply_to(
                message, 
                "🤖 I'm a forwarding bot! I automatically forward messages between chats.\n\n"
                "Use /help to see available commands."
            )
            logger.info(f"💬 Responded to general message from user {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error handling other message: {e}")
        logger.error(traceback.format_exc())

# ==============================================================================
#                 --- MAIN BOT STARTUP WITH ERROR RECOVERY ---
# ==============================================================================

def start_bot():
    """Start the bot with comprehensive error handling"""
    # Validate configuration
    if BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        logger.error("❌ ERROR: Please set BOT_TOKEN in your .env file")
        sys.exit(1)
        
    if SOURCE_CHAT_ID == -1001234567890 or DESTINATION_CHAT_ID == -1009876543210:
        logger.error("❌ ERROR: Please set SOURCE_CHAT_ID and DESTINATION_CHAT_ID in your .env file")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🚀 Starting Telegram Forwarder Bot")
    logger.info(f"📝 Source Chat: {SOURCE_CHAT_ID}")
    logger.info(f"📤 Destination Chat: {DESTINATION_CHAT_ID}")
    logger.info("🌐 Health server: http://0.0.0.0:8000")
    logger.info("⏰ " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries and bot_running:
        try:
            # Test bot connection
            logger.info("🔌 Testing bot connection...")
            bot_info = bot.get_me()
            logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
            
            # Clear any existing webhook to avoid conflicts
            logger.info("🔄 Clearing existing webhooks...")
            bot.remove_webhook()
            time.sleep(1)
            
            # Start polling
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
                break  # Don't retry on conflict
            else:
                logger.error(f"🚨 Telegram API error: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * retry_count
                    logger.info(f"🔄 Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error("❌ Max retries reached. Giving up.")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user (Ctrl+C)")
            break
            
        except Exception as e:
            logger.error(f"🚨 Unexpected error in main loop: {e}")
            logger.error(traceback.format_exc())
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 10 * retry_count
                logger.info(f"🔄 Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error("❌ Max retries reached. Giving up.")

    logger.info("👋 Bot shutdown complete")

if __name__ == '__main__':
    start_bot()
