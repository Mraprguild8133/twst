import logging
import asyncio
import aiohttp
import async_timeout
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json
import hashlib
from dataclasses import dataclass
from enum import Enum
import secrets

from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# Import configuration
from config import config

# Set up structured logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_advanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
class BotState(Enum):
    WAITING_ALBUM = 1

# Data classes
@dataclass
class UploadResult:
    success: bool
    image_url: str = ""
    delete_url: str = ""
    thumbnail_url: str = ""
    error_message: str = ""
    file_hash: str = ""

# Simple in-memory cache
class CacheManager:
    def __init__(self):
        self._memory_cache = {}
        self._rate_limits = {}
    
    async def get(self, key: str):
        return self._memory_cache.get(key)
    
    async def set(self, key: str, value: str, expire: int = 3600):
        self._memory_cache[key] = value
    
    async def incr(self, key: str):
        self._memory_cache[key] = str(int(self._memory_cache.get(key, 0)) + 1)
        return self._memory_cache[key]

# Initialize cache
cache = CacheManager()

# Rate Limiting
class SecurityManager:
    @staticmethod
    async def check_rate_limit(user_id: int) -> bool:
        """Simple rate limiting - 50 requests per hour"""
        key = f"rate_limit:{user_id}:{datetime.now().strftime('%Y%m%d%H')}"
        requests = await cache.incr(key)
        await cache.set(key, str(requests), 3600)
        return requests <= 50
    
    @staticmethod
    def generate_file_hash(file_bytes: BytesIO) -> str:
        """Generate hash for duplicate detection"""
        file_bytes.seek(0)
        return hashlib.md5(file_bytes.read()).hexdigest()

# Advanced Image Processor
class ImageProcessor:
    SUPPORTED_FORMATS = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    
    @staticmethod
    async def validate_image(file_bytes: BytesIO, file_size: int) -> tuple[bool, str]:
        """Comprehensive image validation"""
        if file_size > config.MAX_SIZE_BYTES:
            return False, f"File too large ({file_size / (1024 * 1024):.2f}MB)"
        
        # Basic magic number validation
        file_bytes.seek(0)
        magic = file_bytes.read(4)
        file_bytes.seek(0)
        
        if magic.startswith(b'\xff\xd8\xff'):
            return True, "image/jpeg"
        elif magic.startswith(b'\x89PNG'):
            return True, "image/png"
        elif magic.startswith(b'GIF8'):
            return True, "image/gif"
        elif magic.startswith(b'RIFF') and magic[8:12] == b'WEBP':
            return True, "image/webp"
        
        return False, "Unsupported format"
    
    @staticmethod
    async def optimize_filename(original_name: str) -> str:
        """Generate SEO-friendly filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_str = secrets.token_hex(4)
        return f"upload_{timestamp}_{random_str}.jpg"

# ImgBB API Client with retry logic
class ImgBBClient:
    def __init__(self):
        self.base_url = config.IMGBB_UPLOAD_URL
        self.api_key = config.IMGBB_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def upload_image(
        self, 
        file_bytes: BytesIO, 
        filename: str,
        caption: str = ""
    ) -> UploadResult:
        """Upload image to ImgBB with retry logic"""
        file_hash = SecurityManager.generate_file_hash(file_bytes)
        
        # Check cache for duplicate upload
        cached_result = await cache.get(f"upload:{file_hash}")
        if cached_result:
            logger.info(f"Using cached result for {file_hash}")
            data = json.loads(cached_result)
            return UploadResult(
                success=True,
                image_url=data['url'],
                delete_url=data['delete_url'],
                thumbnail_url=data.get('thumb', {}).get('url', ''),
                file_hash=file_hash
            )
        
        payload = {
            'key': self.api_key,
            'name': filename
        }
        
        if caption:
            payload['description'] = caption
        
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    form_data = aiohttp.FormData()
                    for key, value in payload.items():
                        form_data.add_field(key, value)
                    
                    form_data.add_field(
                        'image', 
                        file_bytes.getvalue(), 
                        filename=filename,
                        content_type='image/jpeg'
                    )
                    
                    async with session.post(self.base_url, data=form_data) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        if data.get('success'):
                            result_data = data['data']
                            result = UploadResult(
                                success=True,
                                image_url=result_data['url'],
                                delete_url=result_data['delete_url'],
                                thumbnail_url=result_data.get('thumb', {}).get('url', ''),
                                file_hash=file_hash
                            )
                            
                            # Cache successful upload
                            await cache.set(
                                f"upload:{file_hash}",
                                json.dumps({
                                    'url': result.image_url,
                                    'delete_url': result.delete_url,
                                    'thumb': {'url': result.thumbnail_url}
                                }),
                                expire=86400  # 24 hours
                            )
                            
                            return result
                        else:
                            return UploadResult(
                                success=False,
                                error_message=data.get('error', {}).get('message', 'Upload failed')
                            )
            
            except asyncio.TimeoutError:
                logger.warning(f"Upload timeout (attempt {attempt + 1})")
                if attempt == 2:
                    return UploadResult(success=False, error_message="Upload timeout")
            
            except Exception as e:
                logger.error(f"Upload error (attempt {attempt + 1}): {e}")
                if attempt == 2:
                    return UploadResult(success=False, error_message=str(e))
            
            await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return UploadResult(success=False, error_message="Max retries exceeded")

# Initialize clients
imgbb_client = ImgBBClient()
image_processor = ImageProcessor()

# Advanced Handlers
class AdvancedHandlers:
    def __init__(self):
        self.upload_semaphore = asyncio.Semaphore(5)  # Limit concurrent uploads
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enhanced start command"""
        user = update.effective_user
        
        welcome_message = (
            f"👋 Welcome *{user.first_name}*!\n\n"
            "I'm your *Advanced Image Uploader Bot* with features:\n"
            "• 🖼️ Single & batch uploads\n"
            "• 📝 Custom captions\n"
            "• 🔄 Duplicate detection\n"
            "• ⚡ Parallel processing\n"
            "• 📊 Usage statistics\n\n"
            f"*File Limit:* {config.MAX_SIZE_MB}MB\n\n"
            "Send images or use /batch for multiple uploads!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📤 Upload Single", callback_data="help_upload")],
            [InlineKeyboardButton("🔄 Batch Upload", callback_data="help_batch")],
            [InlineKeyboardButton("📊 My Stats", callback_data="show_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "help_upload":
            await query.edit_message_text(
                "📤 *Single Upload Help*\n\n"
                "Just send me an image! You can:\n"
                "• Add caption in the message\n"
                "• Multiple formats supported\n"
                "• Automatic optimization\n",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        elif query.data == "help_batch":
            await query.edit_message_text(
                "🔄 *Batch Upload Help*\n\n"
                "Use /batch command to start batch mode.\n"
                "Then send multiple images in sequence.\n"
                "Use /done when finished.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        elif query.data == "show_stats":
            await self.show_stats(update, context)
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user statistics"""
        user_id = update.effective_user.id
        today_key = f"stats:{user_id}:{datetime.now().strftime('%Y%m%d')}"
        
        today_uploads = int(await cache.get(today_key) or 0)
        
        stats_message = (
            "📊 *Your Statistics*\n\n"
            f"• *Today's Uploads:* {today_uploads}\n"
            f"• *Rate Limit:* {await self.get_rate_limit_info(user_id)}"
        )
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                stats_message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                stats_message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
    
    async def get_rate_limit_info(self, user_id: int) -> str:
        """Get rate limit information for user"""
        key = f"rate_limit:{user_id}:{datetime.now().strftime('%Y%m%d%H')}"
        requests = int(await cache.get(key) or 0)
        return f"{requests}/50 per hour"
    
    async def handle_single_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle single photo upload with advanced features"""
        user_id = update.effective_user.id
        
        # Rate limiting check
        if not await SecurityManager.check_rate_limit(user_id):
            await update.message.reply_text("🚫 Rate limit exceeded. Please try again later.")
            return
        
        message = update.message
        photo_file = message.photo[-1]
        caption = message.caption or ""
        
        async with self.upload_semaphore:
            try:
                # Get file info
                file = await context.bot.get_file(photo_file.file_id)
                
                # Validate file size
                if file.file_size > config.MAX_SIZE_BYTES:
                    await message.reply_text(
                        f"🚫 File too large ({file.file_size / (1024 * 1024):.2f}MB). "
                        f"Limit: {config.MAX_SIZE_MB}MB."
                    )
                    return
                
                # Download and process
                file_bytes = BytesIO()
                await file.download_to_memory(file_bytes)
                
                # Validate image
                is_valid, format_info = await image_processor.validate_image(
                    file_bytes, file.file_size
                )
                if not is_valid:
                    await message.reply_text(f"❌ Invalid image: {format_info}")
                    return
                
                # Generate filename
                filename = await image_processor.optimize_filename("upload")
                
                # Upload with progress
                progress_msg = await message.reply_text(
                    f"⚡ Uploading {file.file_size / 1024:.0f}KB image..."
                )
                
                # Upload to ImgBB
                result = await imgbb_client.upload_image(file_bytes, filename, caption)
                
                # Update today's stats
                today_key = f"stats:{user_id}:{datetime.now().strftime('%Y%m%d')}"
                await cache.incr(today_key)
                
                # Send result
                await progress_msg.delete()
                
                if result.success:
                    keyboard = [
                        [InlineKeyboardButton("🌐 Open URL", url=result.image_url)],
                        [InlineKeyboardButton("🗑️ Delete", url=result.delete_url)],
                        [InlineKeyboardButton("📊 Stats", callback_data="show_stats")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    success_msg = (
                        "✅ *Upload Successful!*\n\n"
                        f"• *URL:* `{result.image_url}`\n"
                        f"• *Thumbnail:* [View]({result.thumbnail_url})\n"
                        f"• *Caption:* {caption or 'None'}\n"
                        f"• *Hash:* `{result.file_hash[:8]}`"
                    )
                    
                    await message.reply_text(
                        success_msg,
                        parse_mode=constants.ParseMode.MARKDOWN,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                else:
                    await message.reply_text(f"❌ Upload failed: {result.error_message}")
            
            except Exception as e:
                logger.error(f"Upload error: {e}")
                await message.reply_text("❌ An unexpected error occurred.")
    
    async def batch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start batch upload mode"""
        await update.message.reply_text(
            "🔄 *Batch Upload Mode*\n\n"
            "Send me multiple images one by one.\n"
            "I'll upload them all and provide a summary.\n"
            "Use /done to finish or /cancel to abort.\n\n"
            "You can add captions to each image.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return BotState.WAITING_ALBUM
    
    async def handle_batch_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle photos in batch mode"""
        # Store photo info in context for batch processing
        if 'batch_photos' not in context.user_data:
            context.user_data['batch_photos'] = []
        
        photo_file = update.message.photo[-1]
        context.user_data['batch_photos'].append({
            'file_id': photo_file.file_id,
            'caption': update.message.caption or "",
            'message_id': update.message.message_id
        })
        
        await update.message.reply_text(
            f"✅ Added to batch ({len(context.user_data['batch_photos'])} images). "
            "Send more or /done to finish."
        )
        return BotState.WAITING_ALBUM
    
    async def done_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process batch upload"""
        if 'batch_photos' not in context.user_data or not context.user_data['batch_photos']:
            await update.message.reply_text("No images to upload.")
            return ConversationHandler.END
        
        photos = context.user_data['batch_photos']
        total = len(photos)
        successful = []
        failed = []
        
        progress_msg = await update.message.reply_text(
            f"🔄 Processing {total} images...\n0/{total} completed"
        )
        
        for i, photo_info in enumerate(photos):
            try:
                # Download file
                file = await context.bot.get_file(photo_info['file_id'])
                file_bytes = BytesIO()
                await file.download_to_memory(file_bytes)
                
                # Upload
                filename = await image_processor.optimize_filename(f"batch_{i}")
                result = await imgbb_client.upload_image(
                    file_bytes, filename, photo_info['caption']
                )
                
                if result.success:
                    successful.append(result.image_url)
                else:
                    failed.append(f"Image {i+1}: {result.error_message}")
                
                # Update progress
                await progress_msg.edit_text(
                    f"🔄 Processing {total} images...\n{i+1}/{total} completed\n"
                    f"✅ {len(successful)} successful, ❌ {len(failed)} failed"
                )
                
            except Exception as e:
                failed.append(f"Image {i+1}: {str(e)}")
        
        # Send summary
        summary = f"📊 *Batch Upload Complete*\n\n✅ {len(successful)} successful\n❌ {len(failed)} failed"
        
        if successful:
            summary += "\n\n*Successful Uploads:*\n" + "\n".join(
                f"• `{url}`" for url in successful[:10]  # Limit to first 10
            )
            if len(successful) > 10:
                summary += f"\n• ... and {len(successful) - 10} more"
        
        if failed:
            summary += "\n\n*Failures:*\n" + "\n".join(failed[:5])
            if len(failed) > 5:
                summary += f"\n• ... and {len(failed) - 5} more"
        
        await progress_msg.edit_text(summary, parse_mode=constants.ParseMode.MARKDOWN)
        
        # Cleanup
        context.user_data.pop('batch_photos', None)
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel batch upload"""
        context.user_data.pop('batch_photos', None)
        await update.message.reply_text("❌ Batch upload cancelled.")
        return ConversationHandler.END

# Initialize handlers
advanced_handlers = AdvancedHandlers()

# Main application
def main() -> None:
    """Start the advanced bot"""
    # Validate configuration
    required_config = ['BOT_TOKEN', 'IMGBB_API_KEY', 'MAX_SIZE_BYTES', 'MAX_SIZE_MB']
    for var in required_config:
        if not hasattr(config, var):
            raise ValueError(f"Missing required configuration: {var}")
    
    # Create application
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Conversation handler for batch uploads
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('batch', advanced_handlers.batch_command)],
        states={
            BotState.WAITING_ALBUM: [
                MessageHandler(filters.PHOTO, advanced_handlers.handle_batch_photo),
                CommandHandler('done', advanced_handlers.done_command)
            ],
        },
        fallbacks=[CommandHandler('cancel', advanced_handlers.cancel_command)]
    )
    
    # Register handlers
    application.add_handler(CommandHandler("start", advanced_handlers.start_command))
    application.add_handler(CommandHandler("stats", advanced_handlers.show_stats))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(advanced_handlers.handle_callback))
    application.add_handler(
        MessageHandler(filters.PHOTO & ~filters.COMMAND, advanced_handlers.handle_single_photo)
    )
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting advanced bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in telegram bot"""
    logger.error(f"Exception while handling update: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An internal error occurred. Please try again later."
        )

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        raise