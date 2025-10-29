import os
import asyncio
import logging
from typing import List, Dict
from datetime import datetime

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WasabiStorage:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config.WASABI_ACCESS_KEY,
            aws_secret_access_key=config.WASABI_SECRET_KEY,
            endpoint_url=f'https://s3.{config.WASABI_REGION}.wasabisys.com',
            config=BotoConfig(signature_version='s3v4')
        )
        self.bucket = config.WASABI_BUCKET

    async def upload_file(self, file_path: str, object_name: str) -> bool:
        """Upload file to Wasabi with progress tracking"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Upload with progress (simplified for async)
            self.s3_client.upload_file(
                file_path,
                self.bucket,
                object_name,
                Callback=ProgressPercentage(file_path, object_name)
            )
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    async def download_file(self, object_name: str, file_path: str) -> bool:
        """Download file from Wasabi"""
        try:
            self.s3_client.download_file(
                self.bucket,
                object_name,
                file_path
            )
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        """Generate presigned URL for streaming"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"URL generation failed: {e}")
            return None

    def list_files(self, prefix: str = "") -> List[Dict]:
        """List files in Wasabi bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            return response.get('Contents', [])
        except ClientError as e:
            logger.error(f"List files failed: {e}")
            return []

class ProgressPercentage:
    """Progress callback for S3 uploads/downloads"""
    def __init__(self, filename, operation):
        self._filename = filename
        self._operation = operation
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0

    def __call__(self, bytes_amount):
        self._seen_so_far += bytes_amount
        percentage = (self._seen_so_far / self._size) * 100
        logger.info(f"{self._operation} progress: {percentage:.2f}%")

class TelegramBot:
    def __init__(self):
        self.app = Client(
            "wasabi_bot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN
        )
        self.wasabi = WasabiStorage()
        self.setup_handlers()

    def setup_handlers(self):
        """Setup message handlers"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message: Message):
            await message.reply_text(
                "🤖 **Wasabi Storage Bot**\n\n"
                "I can handle files up to 4GB and provide streaming links!\n\n"
                "**Commands:**\n"
                "/upload - Upload a file\n"
                "/download - Download a file\n"
                "/list - List stored files\n"
                "/stream - Get streaming link\n"
                "/help - Show this help message"
            )

        @self.app.on_message(filters.command("upload") & filters.private)
        async def upload_command(client, message: Message):
            if message.from_user.id not in config.ADMIN_IDS:
                await message.reply_text("❌ Access denied!")
                return
            
            if not message.reply_to_message or not message.reply_to_message.document:
                await message.reply_text("📎 Please reply to a file with /upload")
                return
            
            await self.handle_upload(message)

        @self.app.on_message(filters.command("download") & filters.private)
        async def download_command(client, message: Message):
            if message.from_user.id not in config.ADMIN_IDS:
                await message.reply_text("❌ Access denied!")
                return
            
            if len(message.command) < 2:
                await message.reply_text("📝 Usage: /download <filename>")
                return
            
            await self.handle_download(message)

        @self.app.on_message(filters.command("list") & filters.private)
        async def list_command(client, message: Message):
            if message.from_user.id not in config.ADMIN_IDS:
                await message.reply_text("❌ Access denied!")
                return
            
            await self.handle_list(message)

        @self.app.on_message(filters.command("stream") & filters.private)
        async def stream_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("📝 Usage: /stream <filename>")
                return
            
            await self.handle_stream(message)

    async def handle_upload(self, message: Message):
        """Handle file upload to Wasabi"""
        try:
            msg = await message.reply_text("📤 Starting upload...")
            
            file = message.reply_to_message.document
            if file.file_size > config.MAX_FILE_SIZE:
                await msg.edit_text("❌ File too large! Max 4GB supported.")
                return

            # Download file
            download_path = f"downloads/{file.file_name}"
            os.makedirs("downloads", exist_ok=True)
            
            await msg.edit_text("⬇️ Downloading file...")
            await message.reply_to_message.download(download_path)
            
            # Upload to Wasabi
            await msg.edit_text("☁️ Uploading to Wasabi...")
            object_name = f"telegram/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.file_name}"
            
            success = await self.wasabi.upload_file(download_path, object_name)
            
            if success:
                # Clean up local file
                os.remove(download_path)
                
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎬 Stream Link", callback_data=f"stream_{object_name}"),
                    InlineKeyboardButton("📥 Download", callback_data=f"download_{object_name}")
                ]])
                
                await msg.edit_text(
                    f"✅ **Upload Successful!**\n\n"
                    f"**File:** `{file.file_name}`\n"
                    f"**Size:** {self.format_size(file.file_size)}\n"
                    f"**Storage Key:** `{object_name}`",
                    reply_markup=keyboard
                )
            else:
                await msg.edit_text("❌ Upload failed!")
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")

    async def handle_download(self, message: Message):
        """Handle file download from Wasabi"""
        try:
            filename = message.command[1]
            msg = await message.reply_text("📥 Downloading from Wasabi...")
            
            download_path = f"downloads/{filename}"
            os.makedirs("downloads", exist_ok=True)
            
            success = await self.wasabi.download_file(filename, download_path)
            
            if success and os.path.exists(download_path):
                await msg.edit_text("📤 Sending file...")
                await message.reply_document(
                    download_path,
                    caption=f"📁 {filename}"
                )
                os.remove(download_path)
                await msg.delete()
            else:
                await msg.edit_text("❌ File not found or download failed!")
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")

    async def handle_list(self, message: Message):
        """List files in Wasabi bucket"""
        try:
            msg = await message.reply_text("📂 Listing files...")
            
            files = self.wasabi.list_files("telegram/")
            if not files:
                await msg.edit_text("📭 No files found!")
                return
            
            file_list = "**📁 Stored Files:**\n\n"
            for file in files[:20]:  # Show first 20 files
                size = self.format_size(file['Size'])
                file_list += f"• `{file['Key']}` ({size})\n"
            
            if len(files) > 20:
                file_list += f"\n... and {len(files) - 20} more files"
            
            await msg.edit_text(file_list)
            
        except Exception as e:
            logger.error(f"List error: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")

    async def handle_stream(self, message: Message):
        """Generate streaming links"""
        try:
            filename = message.command[1]
            msg = await message.reply_text("🔗 Generating streaming links...")
            
            stream_url = self.wasabi.generate_presigned_url(filename)
            
            if stream_url:
                # Create media player links
                players = self.generate_player_links(stream_url, filename)
                
                response_text = f"**🎬 Streaming Links for `{filename}`**\n\n"
                response_text += f"**Direct URL:**\n`{stream_url}`\n\n"
                response_text += "**Media Players:**\n"
                
                keyboard_buttons = []
                for player_name, player_url in players.items():
                    response_text += f"• [{player_name}]({player_url})\n"
                    keyboard_buttons.append(
                        [InlineKeyboardButton(f"▶️ {player_name}", url=player_url)]
                    )
                
                await msg.edit_text(
                    response_text,
                    reply_markup=InlineKeyboardMarkup(keyboard_buttons),
                    disable_web_page_preview=True
                )
            else:
                await msg.edit_text("❌ Failed to generate streaming link!")
                
        except Exception as e:
            logger.error(f"Stream error: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")

    def generate_player_links(self, stream_url: str, filename: str) -> Dict[str, str]:
        """Generate links for various media players"""
        encoded_url = stream_url.replace('=', '%3D').replace('&', '%26')
        
        players = {
            "MX Player": f"intent:{stream_url}#Intent;package=com.mxtech.videoplayer.ad;end",
            "VLC": f"vlc://{stream_url}",
            "PotPlayer": f"potplayer://{stream_url}",
            "MPV": f"mpv://{stream_url}",
            "nPlayer": f"nplayer-{stream_url}",
            "Infuse": f"infuse://x-callback-url/play?url={encoded_url}",
            "Kodi": f"kodi://{stream_url}",
            "Jellyfin": f"jellyfin://{stream_url}",
            "Plex": f"plex://{stream_url}"
        }
        
        return players

    def format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.2f} {size_names[i]}"

    async def run(self):
        """Start the bot"""
        await self.app.start()
        logger.info("Bot started successfully!")
        await self.app.idle()

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.run())
