import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import settings
from handlers import advanced_handlers
from cache import cache_manager

# Enhanced logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_advanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedImageBot:
    """High-performance Telegram bot with advanced features"""
    
    def __init__(self):
        self.application = Application.builder().token(settings.BOT_TOKEN).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all advanced handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", advanced_handlers.advanced_start))
        self.application.add_handler(CommandHandler("stats", advanced_handlers.user_stats))
        self.application.add_handler(CommandHandler("batch", advanced_handlers.batch_upload))
        
        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.PHOTO & ~filters.COMMAND, 
                         advanced_handlers.handle_advanced_upload)
        )
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(advanced_handlers.handle_callback))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Exception while handling update: {context.error}")
    
    def run(self):
        """Start the bot with enhanced configuration"""
        logger.info("🚀 Starting Advanced Image Uploader Bot...")
        self.application.run_polling(
            poll_interval=0.5,  # Faster polling
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == '__main__':
    bot = AdvancedImageBot()
    bot.run()
