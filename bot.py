import telebot
import time
import logging
import sys
import signal
import threading
from datetime import datetime
from flask import Flask, jsonify
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
#                 --- HEALTH CHECK SERVER (PORT 8000) ---
# ==============================================================================

def create_health_server():
    """Create a simple health check server on port 8000"""
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
        return jsonify({
            "status": "healthy",
            "service": "telegram-forwarder-bot",
            "timestamp": datetime.now().isoformat()
        })
    
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
                "uptime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "last_restart": datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
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
    try:
        app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")

# Start health server in a separate thread
health_thread = threading.Thread(target=create_health_server, daemon=True)
health_thread.start()

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
            "/health - Health check\n"
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
            f"**Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "**Health Check:** http://localhost:8000/health"
        )
        
        bot.reply_to(message, status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in status handler: {e}")

@bot.message_handler(commands=['health'])
def handle_health(message):
    """Handle /health command"""
    try:
        health_text = (
            "❤️ **Health Status** ❤️\n\n"
            "✅ **Bot:** Running\n"
            "✅ **API:** Connected\n"
            "✅ **Forwarding:** Active\n"
            f"⏰ **Last Check:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            "All systems operational! 🚀"
        )
        
        bot.reply_to(message, health_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in health handler: {e}")

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
            
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"❌ Telegram API error: {e}")
    except Exception as e:
        logger.error(f"❌ Error forwarding message: {e}")

# ==============================================================================
#                 --- ERROR HANDLER ---
# ==============================================================================

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Handle all other messages"""
    if message.chat.type == 'private' and not message.text.startswith('/'):
        bot.reply_to(
            message, 
            "🤖 I'm a forwarding bot! I automatically forward messages between chats.\n\n"
            "Use /help to see available commands."
        )

# ==============================================================================
#                 --- MAIN BOT STARTUP ---
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
    logger.info(f"📝 Source Chat: {SOURCE_CHAT_ID}")
    logger.info(f"📤 Destination Chat: {DESTINATION_CHAT_ID}")
    logger.info("🌐 Health server: http://0.0.0.0:8000")
    logger.info("⏰ " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    try:
        # Test bot connection
        bot_info = bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Clear any existing webhook to avoid conflicts
        bot.remove_webhook()
        time.sleep(0.5)
        
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
