import os
import logging
import requests
import re
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from config import config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class URLShortenerBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.url_cache = {}  # Cache for URL storage
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("shorten", self.shorten))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
    def is_valid_url(self, url: str) -> bool:
        """Enhanced URL validation"""
        pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(pattern, url) is not None
    
    def generate_url_id(self, url: str) -> str:
        """Generate a short unique ID for the URL to avoid long callback data"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return url_hash
    
    def store_url(self, url: str) -> str:
        """Store URL in cache and return short ID"""
        url_id = self.generate_url_id(url)
        self.url_cache[url_id] = url
        return url_id
    
    def get_url(self, url_id: str) -> str:
        """Retrieve URL from cache using short ID"""
        return self.url_cache.get(url_id, '')
    
    async def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors in the telegram bot"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text("❌ An error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Error while sending error message: {e}")

    def is_image_accessible(self, url: str) -> bool:
        """Check if the welcome image URL is accessible"""
        try:
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False

    def shorten_url(self, url, service):
        """Shorten URL using the specified service"""
        try:
            # Validate URL first
            if not self.is_valid_url(url):
                return None

            logger.info(f"Shortening URL with {service}: {url}")

            if service == 'gplinks':
                if not config.GPLINKS_API:
                    logger.error("GPLinks API key not configured")
                    return None
                
                api_url = "https://gplinks.in/api"
                params = {'api': config.GPLINKS_API, 'url': url}
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shortened_url')
                    except ValueError:
                        response_text = response.text.strip()
                        if response_text.startswith('http'):
                            return response_text
                
                return None

            elif service == 'shrinkearn':
                if not config.SHRINKEARN_API:
                    logger.error("ShrinkEarn API key not configured")
                    return None
                
                api_url = "https://shrinkearn.com/api"
                params = {'api': config.SHRINKEARN_API, 'url': url}
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shortened_url')
                    except ValueError:
                        response_text = response.text.strip()
                        if response_text.startswith('http'):
                            return response_text
                
                return None

            elif service == 'shrtfly':
                if not config.SHRTFLY_API:
                    logger.error("ShrtFly API key not configured")
                    return None
                
                api_url = "https://shrtfly.com/api"
                params = {'api': config.SHRTFLY_API, 'url': url}
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shortened_url')
                    except ValueError:
                        response_text = response.text.strip()
                        if response_text.startswith('http'):
                            return response_text
                
                return None

            elif service == 'fclc':
                if not config.FCLC_API:
                    logger.error("FC.LC API key not configured")
                    return None
                
                api_url = "https://fc.lc/api"
                params = {'api': config.FCLC_API, 'url': url}
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shortened_url')
                    except ValueError:
                        response_text = response.text.strip()
                        if response_text.startswith('http'):
                            return response_text
                
                return None
            
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while shortening URL with {service}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with {service}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error shortening URL with {service}: {str(e)}")
            return None
    
    async def start(self, update: Update, context: CallbackContext):
        """Send welcome message when command /start is issued"""
        try:
            user = update.effective_user
            
            welcome_text = f"""
👋 Hello {user.mention_html()}!

**Welcome to URL Shortener Bot!** 🌐

I can shorten your long URLs using various services and help you earn money with shortened links!

✨ **Features:**
• Multiple URL shortening services
• Easy-to-use interface
• Monetization options
• Fast and reliable service

📋 **Available Commands:**
/start - Start the bot
/help - Show help message  
/shorten - Shorten a URL
/status - Check API key status

🚀 **Get Started:**
Simply send me a URL or use /shorten command to begin!
            """
            
            # Try to send with image if available and accessible
            image_sent = False
            if config.WELCOME_IMAGE_URL and self.is_image_accessible(config.WELCOME_IMAGE_URL):
                try:
                    await update.message.reply_photo(
                        photo=config.WELCOME_IMAGE_URL,
                        caption=welcome_text,
                        parse_mode='HTML'
                    )
                    image_sent = True
                    logger.info("Welcome image sent successfully")
                except Exception as photo_error:
                    logger.warning(f"Could not send welcome image: {photo_error}")
                    image_sent = False
            
            # If image failed or not available, send text only
            if not image_sent:
                await update.message.reply_html(welcome_text)
                logger.info("Welcome message sent as text (image not available)")
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def help(self, update: Update, context: CallbackContext):
        """Send help message"""
        try:
            help_text = """
🤖 **URL Shortener Bot Help Guide**

📖 **How to use:**
1. Send me any long URL directly
2. Or use `/shorten <URL>` command
3. Choose your preferred shortening service
4. Get your shortened link instantly!

🔗 **Example:**
`/shorten https://www.example.com/very-long-url-path`

🛠 **Supported Services:**
✅ **GPLinks** - Earn money from your shortened links!
✅ **ShrinkEarn** - Monetize your URLs with ads
✅ **ShrtFly** - Fast and reliable URL shortening
✅ **FC.LC** - Premium URL shortening service

💰 **Monetization:**
With these services, you can earn revenue from every click!
Sign up on their respective websites for API keys.

🔧 **Need Help?**
Use `/status` to check your API key configuration.
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def status(self, update: Update, context: CallbackContext):
        """Check API key status"""
        try:
            status_text = "🔧 **API Key Status**\n\n"
            
            for service_key, service_info in config.SUPPORTED_SERVICES.items():
                service_name = service_info['name']
                requires_key = service_info['requires_key']
                
                if service_key == 'gplinks':
                    has_key = bool(config.GPLINKS_API)
                    key_preview = config.GPLINKS_API[:8] + '...' if has_key and len(config.GPLINKS_API) > 8 else ('Set' if has_key else 'Not set')
                elif service_key == 'shrinkearn':
                    has_key = bool(config.SHRINKEARN_API)
                    key_preview = config.SHRINKEARN_API[:8] + '...' if has_key and len(config.SHRINKEARN_API) > 8 else ('Set' if has_key else 'Not set')
                elif service_key == 'shrtfly':
                    has_key = bool(config.SHRTFLY_API)
                    key_preview = config.SHRTFLY_API[:8] + '...' if has_key and len(config.SHRTFLY_API) > 8 else ('Set' if has_key else 'Not set')
                elif service_key == 'fclc':
                    has_key = bool(config.FCLC_API)
                    key_preview = config.FCLC_API[:8] + '...' if has_key and len(config.FCLC_API) > 8 else ('Set' if has_key else 'Not set')
                else:
                    has_key = True
                    key_preview = "Not required"
                
                status_text += f"**{service_name}**: "
                if requires_key:
                    status_text += "✅" if has_key else "❌"
                else:
                    status_text += "✅"
                status_text += f" ({key_preview})\n"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Error checking status")
    
    async def shorten(self, update: Update, context: CallbackContext):
        """Shorten URL from command"""
        try:
            if not context.args:
                await update.message.reply_text("Please provide a URL to shorten. Usage: `/shorten <URL>`", parse_mode='Markdown')
                return
            
            url = ' '.join(context.args)
            await self.process_url(update, url)
        except Exception as e:
            logger.error(f"Error in shorten command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle messages containing URLs"""
        try:
            url = update.message.text.strip()
            
            if not (url.startswith('http://') or url.startswith('https://')):
                await update.message.reply_text("Please send a valid URL starting with http:// or https://")
                return
            
            await self.process_url(update, url)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def process_url(self, update: Update, url: str):
        """Process URL and generate shortened versions"""
        try:
            # Validate URL
            if not self.is_valid_url(url):
                await update.message.reply_text("❌ Please provide a valid URL starting with http:// or https://")
                return
            
            # Show typing action
            await update.message.reply_chat_action(action="typing")
            
            # Store URL and get short ID
            url_id = self.store_url(url)
            
            # Create keyboard with service options
            keyboard = [
                [
                    InlineKeyboardButton("💰 GPLinks", callback_data=f"s_gpl_{url_id}"),
                    InlineKeyboardButton("💵 ShrinkEarn", callback_data=f"s_shrink_{url_id}"),
                ],
                [
                    InlineKeyboardButton("🚀 ShrtFly", callback_data=f"s_shrt_{url_id}"),
                    InlineKeyboardButton("🔗 FC.LC", callback_data=f"s_fclc_{url_id}"),
                ],
                [InlineKeyboardButton("🎯 All Services", callback_data=f"s_all_{url_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Truncate long URLs for display
            display_url = url
            if len(url) > 50:
                display_url = url[:47] + "..."
            
            await update.message.reply_text(
                f"🔗 **Original URL:**\n`{display_url}`\n\n**Choose a service to shorten:**",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text("❌ An error occurred while processing your URL. Please try again.")
    
    async def button_handler(self, update: Update, context: CallbackContext):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            logger.info(f"Callback data received: {data}")
            
            if data.startswith('s_'):
                parts = data.split('_', 2)
                if len(parts) == 3:
                    _, service_code, url_id = parts
                    
                    # Map short service codes to full service names
                    service_map = {
                        'gpl': 'gplinks',
                        'shrink': 'shrinkearn',
                        'shrt': 'shrtfly',
                        'fclc': 'fclc',
                        'all': 'all'
                    }
                    
                    service = service_map.get(service_code, service_code)
                    url = self.get_url(url_id)
                    
                    if not url:
                        await query.edit_message_text("❌ URL not found. Please try again.")
                        return
                    
                    # Show typing action
                    await query.message.reply_chat_action(action="typing")
                    
                    if service == 'all':
                        await self.send_all_shortened_urls(query, url)
                    else:
                        await self.send_single_shortened_url(query, url, service)
                else:
                    await query.edit_message_text("❌ Invalid request. Please try again.")
            else:
                await query.edit_message_text("❌ Unknown command. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            try:
                await query.edit_message_text("❌ An error occurred. Please try again.")
            except Exception as edit_error:
                logger.error(f"Could not edit message: {edit_error}")
                try:
                    await query.message.reply_text("❌ An error occurred. Please try again.")
                except Exception as send_error:
                    logger.error(f"Could not send message: {send_error}")
    
    async def send_single_shortened_url(self, query, url: str, service: str):
        """Send shortened URL from a single service"""
        try:
            service_info = config.SUPPORTED_SERVICES.get(service, {})
            service_name = service_info.get('name', service.capitalize())
            
            shortened_url = self.shorten_url(url, service)
            
            if shortened_url:
                message = f"✅ **{service_name}**\n🔗 `{shortened_url}`"
                
                if service in ['gplinks', 'shrinkearn', 'shrtfly', 'fclc']:
                    message += "\n\n💰 *Earn money with this shortened link!*"
                
                # Check if message content is different before editing
                current_text = query.message.text if query.message.text else ""
                if message != current_text:
                    await query.edit_message_text(
                        text=message,
                        disable_web_page_preview=True,
                        parse_mode='Markdown'
                    )
                else:
                    # If same content, just send as new message
                    await query.message.reply_text(
                        text=message,
                        disable_web_page_preview=True,
                        parse_mode='Markdown'
                    )
            else:
                error_msg = f"❌ Failed to shorten URL using {service_name}."
                
                if service_info.get('requires_key', True):
                    error_msg += "\n🔑 API key might not be configured or service unavailable."
                else:
                    error_msg += " Service might be temporarily unavailable."
                
                current_text = query.message.text if query.message.text else ""
                if error_msg != current_text:
                    await query.edit_message_text(text=error_msg)
                else:
                    await query.message.reply_text(text=error_msg)
        except Exception as e:
            logger.error(f"Error sending single shortened URL: {e}")
            try:
                await query.edit_message_text("❌ Error generating shortened URL. Please try again.")
            except Exception as edit_error:
                await query.message.reply_text("❌ Error generating shortened URL. Please try again.")
    
    async def send_all_shortened_urls(self, query, url: str):
        """Send shortened URLs from all available services"""
        try:
            message = "🔗 **Shortened URLs**\n\n"
            successful_shortens = 0
            
            for service_key, service_info in config.SUPPORTED_SERVICES.items():
                service_name = service_info.get('name', service_key.capitalize())
                shortened_url = self.shorten_url(url, service_key)
                
                if shortened_url:
                    message += f"✅ **{service_name}**\n`{shortened_url}`"
                    if service_key in ['gplinks', 'shrinkearn', 'shrtfly', 'fclc']:
                        message += " 💰"
                    message += "\n\n"
                    successful_shortens += 1
                else:
                    message += f"❌ **{service_name}** - Failed\n\n"
            
            if successful_shortens == 0:
                message = "❌ All services failed. Please try again later or check your API keys using /status command."
            else:
                message += f"✅ **{successful_shortens}/{len(config.SUPPORTED_SERVICES)} services successful**"
            
            # Check if message content is different before editing
            current_text = query.message.text if query.message.text else ""
            if message != current_text:
                await query.edit_message_text(
                    text=message,
                    disable_web_page_preview=True,
                    parse_mode='Markdown'
                )
            else:
                # If same content, send as new message instead of editing
                await query.message.reply_text(
                    text=message,
                    disable_web_page_preview=True,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error sending all shortened URLs: {e}")
            try:
                # Try to send as new message instead of editing
                await query.message.reply_text(
                    "❌ Error generating shortened URLs. Please try again.",
                    disable_web_page_preview=True
                )
            except Exception as send_error:
                logger.error(f"Could not send error message: {send_error}")
    
    def run_webhook(self):
        """Start the bot with webhook (Render-compatible)"""
        try:
            logger.info(f"Starting URL Shortener Bot with webhook on port {config.WEBHOOK_PORT}...")
            
            # Set webhook explicitly first
            if config.WEBHOOK_URL:
                webhook_url = f"{config.WEBHOOK_URL}/{self.token}"
                logger.info(f"Setting webhook to: {webhook_url}")
                
                # Set the webhook
                self.application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
                
                # Run the webhook server
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=config.WEBHOOK_PORT,
                    webhook_url=webhook_url,
                    url_path=self.token
                )
            else:
                # Fallback for Render without explicit WEBHOOK_URL
                logger.info("Using Render's default webhook configuration")
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=config.WEBHOOK_PORT,
                    url_path=self.token,
                    webhook_url=None
                )
                
        except Exception as e:
            logger.error(f"Error starting webhook: {e}")
            raise

    def run_polling(self):
        """Alternative polling method for development"""
        logger.info("Starting bot with polling...")
        self.application.run_polling()

def check_api_keys():
    """Check if API keys are properly set"""
    print("🔑 Checking API Key Configuration:")
    
    required_keys = [
        ('GPLINKS_API', config.GPLINKS_API),
        ('SHRINKEARN_API', config.SHRINKEARN_API),
        ('SHRTFLY_API', config.SHRTFLY_API),
        ('FCLC_API', config.FCLC_API),
    ]
    
    placeholder_keys = ['your_gplinks_api_key_here', 'your_shrinkearn_api_key_here', 'your_shrtfly_api_key_here', 'your_fclc_api_key_here']
    
    for key_name, key_value in required_keys:
        if key_value and key_value not in placeholder_keys and key_value.strip():
            print(f"   ✅ {key_name}: Configured")
        else:
            print(f"   ❌ {key_name}: Not configured (using placeholder)")

def main():
    """Main function to run the bot"""
    try:
        if not config.BOT_TOKEN:
            print("❌ Error: Please set BOT_TOKEN environment variable")
            return
        
        print("🤖 URL Shortener Bot Starting...")
        
        # Check API keys
        check_api_keys()
        
        # Check if we should use webhook or polling
        if config.USE_WEBHOOK:
            print("🌐 Webhook Mode: Enabled")
            print(f"📡 Webhook URL: {config.WEBHOOK_URL if config.WEBHOOK_URL else 'Using Render default'}")
        else:
            print("🔄 Polling Mode: Enabled")
        
        print("📊 Supported Services:")
        
        # Check welcome image accessibility
        if config.WELCOME_IMAGE_URL:
            bot_temp = URLShortenerBot(config.BOT_TOKEN)
            if bot_temp.is_image_accessible(config.WELCOME_IMAGE_URL):
                print(f"✅ Welcome image is accessible: {config.WELCOME_IMAGE_URL}")
            else:
                print(f"❌ Welcome image not accessible, will use text only: {config.WELCOME_IMAGE_URL}")
        
        for service, info in config.SUPPORTED_SERVICES.items():
            status = "✅" if not info['requires_key'] or (
                (service == 'gplinks' and config.GPLINKS_API and config.GPLINKS_API not in ['', 'your_gplinks_api_key_here']) or
                (service == 'shrinkearn' and config.SHRINKEARN_API and config.SHRINKEARN_API not in ['', 'your_shrinkearn_api_key_here']) or
                (service == 'shrtfly' and config.SHRTFLY_API and config.SHRTFLY_API not in ['', 'your_shrtfly_api_key_here']) or
                (service == 'fclc' and config.FCLC_API and config.FCLC_API not in ['', 'your_fclc_api_key_here'])
            ) else "❌"
            print(f"   {status} {info['name']}")
        
        bot = URLShortenerBot(config.BOT_TOKEN)
        
        if config.USE_WEBHOOK:
            print(f"🚀 Starting webhook server on port {config.WEBHOOK_PORT}...")
            bot.run_webhook()
        else:
            print("🔄 Starting polling...")
            bot.run_polling()
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()