import asyncio
import logging
import os
import time
from typing import Optional, Dict, Any
from urllib.parse import quote

# Telegram imports
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FilePartMissing, RPCError

# Wasabi/AWS imports
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import aiofiles

from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramWasabiBot:
    def __init__(self):
        # Validate configuration
        config.validate()
        
        # Initialize Telegram bot
        self.app = Client(
            "wasabi_bot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN
        )
        
        # Initialize Wasabi client
        self.wasabi_client = self._init_wasabi_client()
        
        # Store upload progress
        self.upload_progress: Dict[int, Dict[str, Any]] = {}
        
        self._register_handlers()
    
    def _init_wasabi_client(self):
        """Initialize Wasabi S3 client with proper configuration"""
        wasabi_endpoint = f"https://s3.{config.WASABI_REGION}.wasabisys.com"
        
        boto_config = Config(
            region_name=config.WASABI_REGION,
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        return boto3.client(
            's3',
            endpoint_url=wasabi_endpoint,
            aws_access_key_id=config.WASABI_ACCESS_KEY,
            aws_secret_access_key=config.WASABI_SECRET_KEY,
            config=boto_config
        )
    
    def _register_handlers(self):
        """Register Telegram message handlers"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message: Message):
            """Handle /start command"""
            welcome_text = (
                "🤖 **Welcome to File Storage Bot!**\n\n"
                "I can help you store files up to 4GB on Wasabi cloud storage.\n\n"
                "**Features:**\n"
                "• Upload any file type\n"
                "• High-speed downloads\n"
                "• Secure cloud storage\n"
                "• Direct download links\n\n"
                "**Just send me any file to get started!**\n\n"
                f"**Verification Required:** {config.VERIFICATION_URL}"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 Upload Files", callback_data="upload_help")],
                [InlineKeyboardButton("🔗 Get Verification", url=config.VERIFICATION_URL)]
            ])
            
            await message.reply_text(welcome_text, reply_markup=keyboard)
        
        @self.app.on_message(filters.document | filters.video | filters.audio | filters.photo)
        async def handle_files(client, message: Message):
            """Handle all file types"""
            await self.process_file_upload(message)
        
        @self.app.on_callback_query()
        async def handle_callbacks(client, callback_query):
            """Handle button callbacks"""
            if callback_query.data == "upload_help":
                help_text = (
                    "**How to upload files:**\n\n"
                    "1. Simply send me any file (document, video, audio, photo)\n"
                    "2. Wait for upload to complete\n"
                    "3. Get your direct download link\n"
                    "4. Share with anyone!\n\n"
                    "**Max file size:** 4GB\n"
                    f"**Verification:** {config.VERIFICATION_URL}"
                )
                await callback_query.message.edit_text(help_text)
    
    async def download_telegram_file(self, message: Message, file_path: str) -> Optional[str]:
        """Download file from Telegram with progress"""
        try:
            if message.document:
                file_size = message.document.file_size
                file_name = message.document.file_name
                file_id = message.document.file_id
            elif message.video:
                file_size = message.video.file_size
                file_name = message.video.file_name or f"video_{message.id}.mp4"
                file_id = message.video.file_id
            elif message.audio:
                file_size = message.audio.file_size
                file_name = message.audio.file_name or f"audio_{message.id}.mp3"
                file_id = message.audio.file_id
            elif message.photo:
                file_size = message.photo.file_size
                file_name = f"photo_{message.id}.jpg"
                file_id = message.photo.file_id
            else:
                await message.reply_text("❌ Unsupported file type")
                return None
            
            # Check file size
            if file_size > config.MAX_FILE_SIZE:
                await message.reply_text(f"❌ File too large. Max size: 4GB")
                return None
            
            # Download file
            download_msg = await message.reply_text(
                f"📥 Downloading: `{file_name}`\n"
                f"📦 Size: {self._format_size(file_size)}\n"
                "⏳ Progress: 0%"
            )
            
            start_time = time.time()
            downloaded = 0
            
            async def progress(current, total):
                nonlocal downloaded
                downloaded = current
                percent = (current / total) * 100
                elapsed = time.time() - start_time
                
                if elapsed > 0:
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    
                    progress_text = (
                        f"📥 Downloading: `{file_name}`\n"
                        f"📦 Size: {self._format_size(total)}\n"
                        f"⏳ Progress: {percent:.1f}%\n"
                        f"🚀 Speed: {self._format_size(speed)}/s\n"
                        f"⏰ ETA: {self._format_time(eta)}"
                    )
                    
                    try:
                        await download_msg.edit_text(progress_text)
                    except:
                        pass
            
            file_path = await message.download(
                file_name=file_path,
                progress=progress
            )
            
            await download_msg.edit_text("✅ Download completed! Now uploading to Wasabi...")
            return file_path
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await message.reply_text("❌ Error downloading file")
            return None
    
    async def upload_to_wasabi(self, file_path: str, file_name: str, message: Message) -> Optional[str]:
        """Upload file to Wasabi with progress"""
        try:
            # Generate unique key for Wasabi
            import uuid
            file_extension = os.path.splitext(file_name)[1]
            wasabi_key = f"telegram-files/{uuid.uuid4()}{file_extension}"
            
            upload_msg = await message.reply_text(
                f"☁️ Uploading to Wasabi: `{file_name}`\n"
                "⏳ Progress: 0%"
            )
            
            file_size = os.path.getsize(file_path)
            start_time = time.time()
            
            def upload_progress_callback(bytes_amount):
                percent = (bytes_amount / file_size) * 100
                elapsed = time.time() - start_time
                
                if elapsed > 0:
                    speed = bytes_amount / elapsed
                    eta = (file_size - bytes_amount) / speed if speed > 0 else 0
                    
                    progress_text = (
                        f"☁️ Uploading to Wasabi: `{file_name}`\n"
                        f"📦 Size: {self._format_size(file_size)}\n"
                        f"⏳ Progress: {percent:.1f}%\n"
                        f"🚀 Speed: {self._format_size(speed)}/s\n"
                        f"⏰ ETA: {self._format_time(eta)}"
                    )
                    
                    # Update progress message (this runs in separate thread)
                    asyncio.create_task(self._update_progress_message(upload_msg, progress_text))
            
            # Upload to Wasabi
            self.wasabi_client.upload_file(
                file_path,
                config.WASABI_BUCKET,
                wasabi_key,
                Callback=upload_progress_callback
            )
            
            # Generate presigned URL (valid for 7 days)
            download_url = self.wasabi_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': config.WASABI_BUCKET, 'Key': wasabi_key},
                ExpiresIn=604800  # 7 days
            )
            
            await upload_msg.delete()
            return download_url
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await message.reply_text("❌ Error uploading to Wasabi")
            return None
    
    async def _update_progress_message(self, message: Message, text: str):
        """Update progress message safely"""
        try:
            await message.edit_text(text)
        except:
            pass
    
    async def process_file_upload(self, message: Message):
        """Main file upload processing function"""
        try:
            # Create temp directory
            os.makedirs("temp", exist_ok=True)
            
            # Generate temp file path
            temp_file = f"temp/temp_{message.id}_{int(time.time())}"
            
            # Step 1: Download from Telegram
            file_path = await self.download_telegram_file(message, temp_file)
            if not file_path:
                return
            
            # Get file name
            if message.document:
                file_name = message.document.file_name
            elif message.video:
                file_name = message.video.file_name or "video.mp4"
            elif message.audio:
                file_name = message.audio.file_name or "audio.mp3"
            else:
                file_name = os.path.basename(file_path)
            
            # Step 2: Upload to Wasabi
            download_url = await self.upload_to_wasabi(file_path, file_name, message)
            
            if download_url:
                # Success message with download link
                file_size = os.path.getsize(file_path)
                
                success_text = (
                    f"✅ **File Uploaded Successfully!**\n\n"
                    f"📁 **File Name:** `{file_name}`\n"
                    f"📦 **File Size:** {self._format_size(file_size)}\n"
                    f"🔗 **Download Link:** [Click Here]({download_url})\n\n"
                    f"**Link valid for 7 days**\n"
                    f"**Verification:** {config.VERIFICATION_URL}"
                )
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download File", url=download_url)],
                    [InlineKeyboardButton("🔗 Get Verification", url=config.VERIFICATION_URL)]
                ])
                
                await message.reply_text(
                    success_text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
            
            # Cleanup temp file
            try:
                os.remove(file_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Process error: {e}")
            await message.reply_text("❌ Error processing file")
    
    def _format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def _format_time(self, seconds):
        """Format time in human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
    
    async def start(self):
        """Start the bot"""
        logger.info("Starting Telegram Wasabi Bot...")
        await self.app.start()
        logger.info("Bot started successfully!")
        
        # Get bot info
        me = await self.app.get_me()
        logger.info(f"Bot running as @{me.username}")
        
        # Keep the bot running
        await asyncio.Event().wait()
    
    async def stop(self):
        """Stop the bot"""
        await self.app.stop()
        logger.info("Bot stopped")

# Main execution
if __name__ == "__main__":
    bot = TelegramWasabiBot()
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Received stop signal...")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        asyncio.run(bot.stop())
