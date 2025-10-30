import asyncio
import os
import time
import logging
from typing import Optional
from urllib.parse import urlparse

# Telegram imports
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    RPCError, SessionPasswordNeeded, PhoneCodeInvalid,
    PhoneCodeExpired, FloodWait, BadRequest
)

# Wasabi/AWS imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import config

logger = logging.getLogger(__name__)

class TelegramWasabiBot:
    def __init__(self):
        self.app = None
        self.wasabi_client = None
        self.initialize_bot()
    
    def initialize_bot(self):
        """Initialize bot components with error handling"""
        try:
            # Validate configuration first
            config.validate()
            
            # Initialize Telegram client
            self.app = Client(
                "wasabi_bot",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                bot_token=config.BOT_TOKEN,
                sleep_threshold=60
            )
            
            # Initialize Wasabi client
            self.wasabi_client = self.init_wasabi_client()
            
            # Register handlers
            self.register_handlers()
            
            logger.info("✅ Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise
    
    def init_wasabi_client(self):
        """Initialize Wasabi S3 client"""
        try:
            wasabi_endpoint = f"https://s3.{config.WASABI_REGION}.wasabisys.com"
            
            session = boto3.Session(
                aws_access_key_id=config.WASABI_ACCESS_KEY,
                aws_secret_access_key=config.WASABI_SECRET_KEY
            )
            
            client = session.client(
                's3',
                endpoint_url=wasabi_endpoint,
                region_name=config.WASABI_REGION
            )
            
            # Test connection
            client.head_bucket(Bucket=config.WASABI_BUCKET)
            logger.info("✅ Wasabi connection successful")
            
            return client
            
        except NoCredentialsError:
            logger.error("❌ Wasabi credentials not found")
            raise
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"❌ Bucket '{config.WASABI_BUCKET}' not found")
            elif error_code == 'InvalidAccessKeyId':
                logger.error("❌ Invalid Wasabi access key")
            else:
                logger.error(f"❌ Wasabi connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected Wasabi error: {e}")
            raise
    
    def register_handlers(self):
        """Register message handlers"""
        
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message: Message):
            await self.handle_start(message)
        
        @self.app.on_message(filters.command("help"))
        async def help_handler(client, message: Message):
            await self.handle_help(message)
        
        @self.app.on_message(filters.document | filters.video | filters.audio)
        async def file_handler(client, message: Message):
            await self.handle_file_upload(message)
        
        @self.app.on_message(filters.photo)
        async def photo_handler(client, message: Message):
            await self.handle_photo_upload(message)
    
    async def handle_start(self, message: Message):
        """Handle /start command"""
        try:
            welcome_text = f"""
🤖 **Welcome to File Storage Bot!**

I can help you store files up to 4GB on Wasabi cloud storage.

**Features:**
• Upload any file type
• High-speed downloads  
• Secure cloud storage
• Direct download links

**Just send me any file to get started!**

**Verification Required:** {config.VERIFICATION_URL}
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 Upload Files", callback_data="upload_help")],
                [InlineKeyboardButton("🔗 Get Verification", url=config.VERIFICATION_URL)],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ])
            
            await message.reply_text(welcome_text, reply_markup=keyboard)
            logger.info(f"✅ Start command handled for user {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Error in start handler: {e}")
            await message.reply_text("❌ Sorry, something went wrong!")
    
    async def handle_help(self, message: Message):
        """Handle /help command"""
        help_text = f"""
**📖 How to use this bot:**

1. **Upload Files**: Simply send me any file (document, video, audio, photo)
2. **Auto Processing**: I'll automatically upload it to Wasabi cloud storage
3. **Get Link**: You'll receive a direct download link
4. **Share**: Share the link with anyone!

**📋 Supported Files:**
• Documents (PDF, ZIP, etc.)
• Videos (MP4, AVI, etc.) 
• Audio (MP3, WAV, etc.)
• Photos (JPG, PNG, etc.)

**⚡ Limits:**
• Max file size: 4GB
• Download links valid for 7 days

**🔗 Verification:** {config.VERIFICATION_URL}
        """
        
        await message.reply_text(help_text)
    
    async def handle_file_upload(self, message: Message):
        """Handle document, video, and audio files"""
        try:
            # Get file info
            if message.document:
                file = message.document
                file_type = "document"
            elif message.video:
                file = message.video
                file_type = "video"
            elif message.audio:
                file = message.audio
                file_type = "audio"
            else:
                return
            
            file_name = getattr(file, 'file_name', f'{file_type}_{message.id}')
            file_size = file.file_size
            
            logger.info(f"📥 Processing {file_type}: {file_name} ({self.format_size(file_size)})")
            
            # Check file size
            if file_size > config.MAX_FILE_SIZE:
                await message.reply_text("❌ File too large! Maximum size is 4GB.")
                return
            
            # Start processing
            status_msg = await message.reply_text(
                f"📥 **Downloading File...**\n"
                f"📁 Name: `{file_name}`\n"
                f"📦 Size: {self.format_size(file_size)}\n"
                f"⏳ Status: Starting..."
            )
            
            # Download file
            file_path = await self.download_file(message, file, status_msg)
            if not file_path:
                return
            
            # Upload to Wasabi
            download_url = await self.upload_to_wasabi(file_path, file_name, status_msg)
            
            if download_url:
                # Send success message
                success_text = f"""
✅ **File Uploaded Successfully!**

📁 **File Name:** `{file_name}`
📦 **File Size:** {self.format_size(file_size)}
🔗 **Download Link:** [Click Here]({download_url})

**Link valid for 7 days**
**Verification:** {config.VERIFICATION_URL}
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download File", url=download_url)],
                    [InlineKeyboardButton("🔗 Get Verification", url=config.VERIFICATION_URL)]
                ])
                
                await status_msg.edit_text(
                    success_text, 
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                
                logger.info(f"✅ File uploaded successfully: {file_name}")
            
            # Cleanup
            await self.cleanup_file(file_path)
            
        except Exception as e:
            logger.error(f"❌ Error handling file upload: {e}")
            await message.reply_text("❌ Error processing file. Please try again.")
    
    async def handle_photo_upload(self, message: Message):
        """Handle photo uploads"""
        try:
            photo = message.photo
            file_size = photo.file_size
            file_name = f"photo_{message.id}.jpg"
            
            status_msg = await message.reply_text(
                f"📥 **Downloading Photo...**\n"
                f"📁 Name: `{file_name}`\n" 
                f"📦 Size: {self.format_size(file_size)}\n"
                f"⏳ Status: Starting..."
            )
            
            # Download photo
            file_path = await message.download(file_name=f"temp/{file_name}")
            
            # Upload to Wasabi
            download_url = await self.upload_to_wasabi(file_path, file_name, status_msg)
            
            if download_url:
                success_text = f"""
✅ **Photo Uploaded Successfully!**

📁 **File Name:** `{file_name}`
📦 **File Size:** {self.format_size(file_size)}
🔗 **Download Link:** [Click Here]({download_url})

**Link valid for 7 days**
**Verification:** {config.VERIFICATION_URL}
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download Photo", url=download_url)],
                    [InlineKeyboardButton("🔗 Get Verification", url=config.VERIFICATION_URL)]
                ])
                
                await status_msg.edit_text(
                    success_text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
            
            # Cleanup
            await self.cleanup_file(file_path)
            
        except Exception as e:
            logger.error(f"❌ Error handling photo upload: {e}")
            await message.reply_text("❌ Error processing photo.")
    
    async def download_file(self, message: Message, file, status_msg: Message) -> Optional[str]:
        """Download file from Telegram"""
        try:
            file_name = getattr(file, 'file_name', 'file')
            file_size = file.file_size
            
            def progress(current, total):
                percent = (current / total) * 100
                asyncio.create_task(
                    status_msg.edit_text(
                        f"📥 **Downloading File...**\n"
                        f"📁 Name: `{file_name}`\n"
                        f"📦 Size: {self.format_size(total)}\n"
                        f"⏳ Progress: {percent:.1f}%"
                    )
                )
            
            # Create temp directory
            os.makedirs("temp", exist_ok=True)
            
            file_path = await message.download(
                file_name=f"temp/{file_name}",
                progress=progress
            )
            
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            await status_msg.edit_text("❌ Error downloading file")
            return None
    
    async def upload_to_wasabi(self, file_path: str, file_name: str, status_msg: Message) -> Optional[str]:
        """Upload file to Wasabi storage"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Generate unique key
            import uuid
            file_ext = os.path.splitext(file_name)[1]
            wasabi_key = f"telegram/{uuid.uuid4()}{file_ext}"
            
            await status_msg.edit_text(
                f"☁️ **Uploading to Cloud...**\n"
                f"📁 Name: `{file_name}`\n"
                f"📦 Size: {self.format_size(file_size)}\n"
                f"⏳ Progress: Starting..."
            )
            
            # Upload file
            self.wasabi_client.upload_file(
                file_path,
                config.WASABI_BUCKET,
                wasabi_key,
                ExtraArgs={'ACL': 'public-read'}
            )
            
            # Generate download URL
            download_url = self.wasabi_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': config.WASABI_BUCKET, 'Key': wasabi_key},
                ExpiresIn=604800  # 7 days
            )
            
            return download_url
            
        except Exception as e:
            logger.error(f"❌ Wasabi upload error: {e}")
            await status_msg.edit_text("❌ Error uploading to cloud storage")
            return None
    
    async def cleanup_file(self, file_path: str):
        """Clean up temporary files"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"⚠️ Could not delete temp file: {e}")
    
    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if not size_bytes:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    async def start(self):
        """Start the bot"""
        try:
            logger.info("🚀 Starting Telegram Wasabi Bot...")
            
            await self.app.start()
            
            # Get bot info
            me = await self.app.get_me()
            logger.info(f"✅ Bot running as @{me.username}")
            
            # Start waiting for messages
            await idle()
            
        except RPCError as e:
            logger.error(f"❌ Telegram RPC Error: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        try:
            if self.app:
                await self.app.stop()
            logger.info("🛑 Bot stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")

def main():
    """Main function to run the bot"""
    try:
        # Create temp directory
        os.makedirs("temp", exist_ok=True)
        
        # Initialize and run bot
        bot = TelegramWasabiBot()
        
        # Run the bot
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
