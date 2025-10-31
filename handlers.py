import asyncio
import time
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

class AdvancedHandlers:
    """Advanced bot handlers with high-performance features"""
    
    def __init__(self):
        self.upload_stats: Dict[int, dict] = {}
    
    async def advanced_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with user analytics"""
        user = update.effective_user
        await cache_manager.set_user_quota(user.id, 0)
        
        keyboard = [
            [InlineKeyboardButton("🚀 Quick Upload", callback_data="quick_upload")],
            [InlineKeyboardButton("📊 My Stats", callback_data="user_stats"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("💡 Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            templates.welcome_message(),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_advanced_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """High-performance image upload handler"""
        user = update.effective_user
        message = update.message
        start_time = time.time()
        
        # Rate limiting check
        allowed, retry_after = await rate_limiter.check_rate_limit(user.id)
        if not allowed:
            await message.reply_text(
                templates.error_template("rate_limit").format(time=retry_after),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        async with rate_limiter.upload_throttler:
            try:
                # Get largest photo
                photo_file = await message.photo[-1].get_file()
                
                # Download and process image
                image_data = BytesIO()
                await photo_file.download_to_memory(image_data)
                
                # Optimize image
                optimized_data = await image_processor.optimize_image(image_data)
                
                # Upload to ImgBB
                async with aiohttp.ClientSession() as session:
                    form_data = aiohttp.FormData()
                    form_data.add_field('key', settings.IMGBB_API_KEY)
                    form_data.add_field('image', optimized_data.getvalue(), 
                                      filename='optimized_image.jpg')
                    
                    async with session.post(settings.IMGBB_UPLOAD_URL, data=form_data) as response:
                        result = await response.json()
                
                if result.get('success'):
                    # Calculate stats
                    processing_time = time.time() - start_time
                    original_size = len(image_data.getvalue()) / (1024 * 1024)
                    optimized_size = len(optimized_data.getvalue()) / (1024 * 1024)
                    
                    stats = {
                        'size_mb': optimized_size,
                        'processing_time': processing_time,
                        'optimization_saved': ((original_size - optimized_size) / original_size) * 100
                    }
                    
                    # Send success message
                    image_url = result['data']['url']
                    delete_url = result['data']['delete_url']
                    
                    await message.reply_text(
                        templates.upload_success_template(image_url, stats),
                        reply_markup=templates.create_upload_keyboard(image_url, delete_url),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Update user stats
                    await self._update_user_stats(user.id, stats)
                    
            except Exception as e:
                logger.error(f"Upload error: {e}")
                await message.reply_text(
                    templates.error_template("upload_failed", str(e)),
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def _update_user_stats(self, user_id: int, stats: dict):
        """Update user upload statistics"""
        if user_id not in self.upload_stats:
            self.upload_stats[user_id] = {
                'total_uploads': 0,
                'total_size_mb': 0,
                'total_time_saved': 0
            }
        
        self.upload_stats[user_id]['total_uploads'] += 1
        self.upload_stats[user_id]['total_size_mb'] += stats['size_mb']
        self.upload_stats[user_id]['total_time_saved'] += stats['processing_time']

advanced_handlers = AdvancedHandlers()
