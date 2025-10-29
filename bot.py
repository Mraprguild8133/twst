import os
import time
import boto3
import asyncio
import re
import base64
import sqlite3
from threading import Thread
from contextlib import contextmanager
from flask import Flask, render_template
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, ButtonUrlInvalid
from dotenv import load_dotenv
import logging
from collections import defaultdict
from datetime import datetime, timedelta
import botocore
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
WASABI_BUCKET = os.getenv("WASABI_BUCKET")
WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
RENDER_URL = os.getenv("RENDER_URL", "http://localhost:8000")
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB

# Payment Configuration
MERCHANT_UPI_ID = os.getenv("MERCHANT_UPI_ID", "test@okaxis")
MERCHANT_NAME = os.getenv("MERCHANT_NAME", "Cloud Storage Pro")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "123456789"))

# Premium plans configuration
PREMIUM_PLANS = {
    "basic": {
        "name": "Basic Plan",
        "price": 20,
        "storage_gb": 50,
        "max_file_size_gb": 4,
        "duration_days": 30,
        "features": ["50GB Storage", "4GB File Size", "Priority Support"]
    },
    "pro": {
        "name": "Pro Plan", 
        "price": 40,
        "storage_gb": 200,
        "max_file_size_gb": 10,
        "duration_days": 30,
        "features": ["200GB Storage", "10GB File Size", "24/7 Priority Support"]
    }
}

# Validate environment variables
missing_vars = []
for var_name, var_value in [
    ("API_ID", API_ID),
    ("API_HASH", API_HASH),
    ("BOT_TOKEN", BOT_TOKEN),
    ("WASABI_ACCESS_KEY", WASABI_ACCESS_KEY),
    ("WASABI_SECRET_KEY", WASABI_SECRET_KEY),
    ("WASABI_BUCKET", WASABI_BUCKET),
]:
    if not var_value:
        missing_vars.append(var_name)

if missing_vars:
    raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")

# Initialize clients
app = Client("wasabi_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Configure Wasabi S3 client
try:
    wasabi_endpoint_url = f'https://s3.{WASABI_REGION}.wasabisys.com'
    
    s3_client = boto3.client(
        's3',
        endpoint_url=wasabi_endpoint_url,
        aws_access_key_id=WASABI_ACCESS_KEY,
        aws_secret_access_key=WASABI_SECRET_KEY,
        region_name=WASABI_REGION,
        config=boto3.session.Config(
            s3={'addressing_style': 'virtual'},
            signature_version='s3v4'
        )
    )
    
    # Test connection
    s3_client.head_bucket(Bucket=WASABI_BUCKET)
    logger.info("✅ Successfully connected to Wasabi bucket")
    
except Exception as e:
    logger.error(f"❌ Wasabi connection failed: {e}")
    raise Exception(f"Could not connect to Wasabi: {e}")

# Database setup for premium users
class PremiumManager:
    def __init__(self, db_path="premium_users.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS premium_users (
                    user_id INTEGER PRIMARY KEY,
                    plan_type TEXT NOT NULL,
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP NOT NULL,
                    storage_gb INTEGER NOT NULL,
                    max_file_size_gb INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_user_plan(self, user_id):
        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM premium_users 
                WHERE user_id = ? AND is_active = 1 AND end_date > datetime('now')
            ''', (user_id,)).fetchone()
            return dict(row) if row else None
    
    def is_premium_user(self, user_id):
        return self.get_user_plan(user_id) is not None

# Initialize premium manager
premium_manager = PremiumManager()

# -----------------------------
# Flask app for player.html
# -----------------------------
flask_app = Flask(__name__, template_folder="templates")

@flask_app.route("/")
def index():
    return render_template("index.html")

@flask_app.route("/player/<media_type>/<encoded_url>")
def player(media_type, encoded_url):
    try:
        padding = 4 - (len(encoded_url) % 4)
        if padding != 4:
            encoded_url += '=' * padding
        media_url = base64.urlsafe_b64decode(encoded_url).decode()
        return render_template("player.html", media_type=media_type, media_url=media_url)
    except Exception as e:
        return f"Error decoding URL: {str(e)}", 400

def run_flask():
    flask_app.run(host="0.0.0.0", port=8000, debug=False)

# -----------------------------
# Helper Functions - FIXED URL VALIDATION
# -----------------------------
MEDIA_EXTENSIONS = {
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'],
    'audio': ['.mp3', '.m4a', '.ogg', '.wav', '.flac'],
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
}

def is_valid_url(url):
    """Validate URL format for Telegram buttons"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    for file_type, extensions in MEDIA_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return 'other'

def generate_player_url(filename, presigned_url):
    """Generate player URL with proper validation"""
    if not RENDER_URL or RENDER_URL == "http://localhost:8000":
        return None
    
    file_type = get_file_type(filename)
    if file_type in ['video', 'audio', 'image']:
        try:
            encoded_url = base64.urlsafe_b64encode(presigned_url.encode()).decode().rstrip('=')
            player_url = f"{RENDER_URL}/player/{file_type}/{encoded_url}"
            # Validate the generated URL
            if is_valid_url(player_url):
                return player_url
        except Exception as e:
            logger.error(f"Player URL generation failed: {e}")
    return None

def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < power:
            return f"{size:.2f} {unit}"
        size /= power
    return f"{size:.2f} TB"

def sanitize_filename(filename):
    filename = re.sub(r'[^a-zA-Z0-9 _.-]', '_', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename

def get_user_folder(user_id):
    return f"user_{user_id}"

def create_download_keyboard(presigned_url, player_url=None):
    """Create inline keyboard with URL validation"""
    keyboard = []
    
    # Validate presigned URL
    if presigned_url and is_valid_url(presigned_url):
        keyboard.append([InlineKeyboardButton("📥 Direct Download", url=presigned_url)])
    
    # Validate player URL
    if player_url and is_valid_url(player_url):
        keyboard.append([InlineKeyboardButton("🎬 Web Player", url=player_url)])
    
    # If no valid URLs, return None (no keyboard)
    if not keyboard:
        return None
    
    return InlineKeyboardMarkup(keyboard)

def create_progress_bar(percentage, length=20):
    filled = int(length * percentage / 100)
    empty = length - filled
    return '█' * filled + '○' * empty

def format_eta(seconds):
    if seconds <= 0:
        return "00:00"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    return f"{int(minutes):02d}:{int(seconds):02d}"

def format_elapsed(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

def get_max_file_size(user_id):
    user_plan = premium_manager.get_user_plan(user_id)
    if user_plan:
        return user_plan['max_file_size_gb'] * 1024 * 1024 * 1024
    return MAX_FILE_SIZE

# Rate limiting
user_requests = defaultdict(list)

def is_rate_limited(user_id, limit=5, period=60):
    now = datetime.now()
    user_requests[user_id] = [req_time for req_time in user_requests[user_id] if now - req_time < timedelta(seconds=period)]
    
    if len(user_requests[user_id]) >= limit:
        return True
    
    user_requests[user_id].append(now)
    return False

# -----------------------------
# Bot Handlers - FIXED UPLOAD WITH PROPER ERROR HANDLING
# -----------------------------
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
    
    user_plan = premium_manager.get_user_plan(message.from_user.id)
    plan_status = "🌟 **Premium User**" if user_plan else "⚡ **Free User**"
    
    if user_plan:
        end_date = datetime.strptime(user_plan['end_date'], '%Y-%m-%d %H:%M:%S')
        days_left = (end_date - datetime.now()).days
        plan_status += f"\n📅 Plan: {user_plan['plan_type'].title()}\n⏳ Days Left: {days_left}"
    
    await message.reply_text(
        f"🚀 Cloud Storage Bot with Web Player\n\n"
        f"{plan_status}\n\n"
        "Send me any file to upload to Wasabi storage\n"
        "Use /download <filename> to download files\n"
        "Use /play <filename> to get web player links\n"
        "Use /list to see your files\n"
        "Use /delete <filename> to remove files\n"
        "Use /premium to upgrade to premium\n\n"
        "<b>⚡ Features:</b>\n"
        "• 2GB file size support (Free)\n"
        "• Up to 10GB file size (Premium)\n"
        "• Real-time progress tracking\n"
        "• Web player for media files\n\n"
        "<b>💎 Owner:</b> @Sathishkumar33"
    )

@app.on_message(filters.command("premium"))
async def premium_command(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
    
    if not MERCHANT_UPI_ID or MERCHANT_UPI_ID == "test@okaxis":
        await message.reply_text("❌ Premium features are currently unavailable. Please contact admin.")
        return
    
    user_plan = premium_manager.get_user_plan(message.from_user.id)
    
    if user_plan:
        end_date = datetime.strptime(user_plan['end_date'], '%Y-%m-%d %H:%M:%S')
        days_left = (end_date - datetime.now()).days
        await message.reply_text(
            f"🌟 You already have an active premium plan!\n\n"
            f"📋 Plan: {user_plan['plan_type'].title()}\n"
            f"💾 Storage: {user_plan['storage_gb']}GB\n"
            f"📁 Max File Size: {user_plan['max_file_size_gb']}GB\n"
            f"⏳ Days Left: {days_left}"
        )
        return
    
    plans_text = "💎 **Premium Plans Available:**\n\n"
    for plan_id, plan in PREMIUM_PLANS.items():
        plans_text += f"**{plan['name']}** - ₹{plan['price']}\n"
        plans_text += f"• {plan['storage_gb']}GB Storage\n"
        plans_text += f"• {plan['max_file_size_gb']}GB Max File Size\n"
        plans_text += f"• {plan['duration_days']} Days Access\n"
        for feature in plan['features']:
            plans_text += f"• {feature}\n"
        plans_text += "\n"
    
    plans_text += f"**Payment Method:**\nGPay UPI: `{MERCHANT_UPI_ID}`\n\nContact @Sathishkumar33 for payment."
    
    await message.reply_text(plans_text)

# FIXED UPLOAD HANDLER WITH PROPER URL VALIDATION
@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def upload_file_handler(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    try:
        # Get media object and file info
        if message.document:
            media = message.document
            file_name = media.file_name or f"document_{message.id}.bin"
        elif message.video:
            media = message.video
            file_name = media.file_name or f"video_{message.id}.mp4"
        elif message.audio:
            media = message.audio
            file_name = media.file_name or f"audio_{message.id}.mp3"
        elif message.photo:
            media = message.photo
            file_name = f"photo_{message.id}.jpg"
        else:
            await message.reply_text("❌ Unsupported file type")
            return

        # Get file size
        file_size = media.file_size
        
        # Check file size limit
        max_allowed_size = get_max_file_size(message.from_user.id)
        if file_size > max_allowed_size:
            user_plan = premium_manager.get_user_plan(message.from_user.id)
            if user_plan:
                await message.reply_text(
                    f"❌ File too large. Your premium plan allows up to {user_plan['max_file_size_gb']}GB files.\n"
                    f"📦 Current file: {humanbytes(file_size)}"
                )
            else:
                await message.reply_text(
                    f"❌ File too large. Free users limited to {humanbytes(MAX_FILE_SIZE)}.\n"
                    f"📦 Current file: {humanbytes(file_size)}\n"
                    f"💎 Use /premium to upgrade for larger files!"
                )
            return

        # Sanitize filename
        file_name = sanitize_filename(file_name)
        user_file_name = f"{get_user_folder(message.from_user.id)}/{file_name}"
        
        # Send initial status message
        status_message = await message.reply_text(
            f"📥 **Starting Download...**\n\n"
            f"📁 File: `{file_name}`\n"
            f"📦 Size: {humanbytes(file_size)}\n"
            f"⏳ Status: Downloading from Telegram..."
        )

        download_start_time = time.time()
        last_update_time = time.time()
        processed_bytes = 0
        last_processed_bytes = 0

        async def progress_callback(current, total):
            nonlocal processed_bytes, last_update_time, last_processed_bytes
            processed_bytes = current
            current_time = time.time()
            
            # Update progress every 2 seconds to avoid flooding
            if current_time - last_update_time >= 2:
                percentage = (current / total) * 100
                elapsed_time = current_time - download_start_time
                
                # Calculate speed
                speed = (current - last_processed_bytes) / (current_time - last_update_time)
                
                # Calculate ETA
                if speed > 0:
                    eta = (total - current) / speed
                else:
                    eta = 0
                
                # Format progress message
                progress_bar = create_progress_bar(percentage)
                progress_text = (
                    f"📥 **Downloading...**\n\n"
                    f"📁 File: `{file_name}`\n"
                    f"📦 Progress: [{progress_bar}] {percentage:.1f}%\n"
                    f"💾 Processed: {humanbytes(current)} / {humanbytes(total)}\n"
                    f"🚀 Speed: {humanbytes(speed)}/s\n"
                    f"⏱️ ETA: {format_eta(eta)}\n"
                    f"⏰ Elapsed: {format_elapsed(elapsed_time)}"
                )
                
                try:
                    await status_message.edit_text(progress_text)
                    last_update_time = current_time
                    last_processed_bytes = current
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    logger.warning(f"Progress update failed: {e}")

        # Download file
        try:
            file_path = await message.download(
                file_name=file_name,
                progress=progress_callback
            )
        except Exception as e:
            await status_message.edit_text(f"❌ Download failed: {str(e)}")
            return

        # Update status to uploading
        await status_message.edit_text(
            f"📤 **Uploading to Cloud...**\n\n"
            f"📁 File: `{file_name}`\n"
            f"📦 Size: {humanbytes(file_size)}\n"
            f"⏳ Status: Uploading to Wasabi Storage..."
        )

        # Upload to Wasabi
        upload_start_time = time.time()
        try:
            await asyncio.to_thread(
                s3_client.upload_file,
                file_path,
                WASABI_BUCKET,
                user_file_name
            )
            upload_time = time.time() - upload_start_time
        except Exception as e:
            await status_message.edit_text(f"❌ Upload failed: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        # Generate shareable links with proper validation
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object', 
                Params={'Bucket': WASABI_BUCKET, 'Key': user_file_name}, 
                ExpiresIn=86400  # 24 hours
            )
            
            # Validate presigned URL
            if not is_valid_url(presigned_url):
                logger.warning(f"Invalid presigned URL generated: {presigned_url}")
                presigned_url = None
            
            player_url = None
            if presigned_url:
                player_url = generate_player_url(file_name, presigned_url)
            
            # Create keyboard only if we have valid URLs
            keyboard = None
            if presigned_url or player_url:
                keyboard = create_download_keyboard(presigned_url, player_url)
            
            total_time = time.time() - download_start_time
            
            # Prepare completion message
            premium_status = " 🌟" if premium_manager.is_premium_user(message.from_user.id) else ""
            response_text = (
                f"✅ **Upload Complete!**{premium_status}\n\n"
                f"📁 File: `{file_name}`\n"
                f"📦 Size: {humanbytes(file_size)}\n"
                f"⏱️ Total Time: {format_elapsed(total_time)}\n"
                f"⏰ Link Expires: 24 hours\n"
                f"🔗 Storage: Wasabi Cloud"
            )
            
            # Add download information
            if presigned_url:
                response_text += f"\n\n📥 **Download Available**"
            if player_url:
                response_text += f"\n🎬 **Web Player Available**"
            
            # Send final message with keyboard if available
            if keyboard:
                await status_message.edit_text(response_text, reply_markup=keyboard)
            else:
                # If no valid URLs, provide manual instructions
                response_text += f"\n\n⚠️ **Manual Download:**\nUse /download `{file_name}` to get download link"
                await status_message.edit_text(response_text)
            
        except ButtonUrlInvalid as e:
            # Handle invalid button URLs gracefully
            logger.error(f"Button URL invalid: {e}")
            response_text = (
                f"✅ **Upload Complete!**\n\n"
                f"📁 File: `{file_name}`\n"
                f"📦 Size: {humanbytes(file_size)}\n"
                f"⏱️ Total Time: {format_elapsed(total_time)}\n\n"
                f"⚠️ **Download Instructions:**\n"
                f"Use command: /download `{file_name}`"
            )
            await status_message.edit_text(response_text)
        
        except Exception as e:
            logger.error(f"Link generation failed: {e}")
            response_text = (
                f"✅ **Upload Complete!**\n\n"
                f"📁 File: `{file_name}`\n"
                f"📦 Size: {humanbytes(file_size)}\n"
                f"⏱️ Total Time: {format_elapsed(total_time)}\n\n"
                f"⚠️ **Download Instructions:**\n"
                f"Use command: /download `{file_name}`"
            )
            await status_message.edit_text(response_text)
        
        # Clean up local file
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        logger.error(f"Upload error: {e}")
        try:
            await message.reply_text(f"❌ Upload failed: {str(e)}")
        except:
            pass

# FIXED DOWNLOAD HANDLER
@app.on_message(filters.command("download"))
async def download_file_handler(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    if len(message.command) < 2:
        await message.reply_text("Usage: /download <filename>")
        return

    file_name = " ".join(message.command[1:])
    user_file_name = f"{get_user_folder(message.from_user.id)}/{file_name}"
    
    status_message = await message.reply_text(f"🔍 Searching for file: {file_name}...")
    
    try:
        # Check if file exists
        s3_client.head_object(Bucket=WASABI_BUCKET, Key=user_file_name)
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object', 
            Params={'Bucket': WASABI_BUCKET, 'Key': user_file_name}, 
            ExpiresIn=86400
        )
        
        # Validate URL before creating button
        if not is_valid_url(presigned_url):
            await status_message.edit_text(
                f"❌ Error generating download link for: `{file_name}`\n\n"
                f"Please try again or contact support."
            )
            return
        
        # Generate player URL if supported
        player_url = generate_player_url(file_name, presigned_url)
        
        # Create keyboard with validated URLs
        keyboard = create_download_keyboard(presigned_url, player_url)
        
        response_text = f"📥 **Download Ready**\n\n📁 File: `{file_name}`\n⏰ Link expires: 24 hours"
        
        if player_url:
            response_text += f"\n\n🎬 **Web Player Available**"
        
        # Send message with keyboard if available, otherwise send text only
        if keyboard:
            await status_message.edit_text(response_text, reply_markup=keyboard)
        else:
            response_text += f"\n\n🔗 **Download URL:**\n{presigned_url}"
            await status_message.edit_text(response_text)

    except botocore.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            await status_message.edit_text("❌ File not found.")
        else:
            await status_message.edit_text(f"❌ Storage Error: {str(e)}")
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")

# Other handlers remain the same...
@app.on_message(filters.command("play"))
async def play_file(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: /play <filename>")
            return
            
        filename = " ".join(message.command[1:])
        user_folder = get_user_folder(message.from_user.id)
        user_file_name = f"{user_folder}/{filename}"
        
        # Generate a presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': user_file_name},
            ExpiresIn=86400
        )
        
        player_url = generate_player_url(filename, presigned_url)
        
        if player_url and is_valid_url(player_url):
            await message.reply_text(
                f"🎬 **Web Player Link**\n\n"
                f"📁 File: `{filename}`\n"
                f"🔗 URL: {player_url}\n\n"
                f"⏰ This link will expire in 24 hours."
            )
        else:
            await message.reply_text(
                f"❌ Web player not available for this file.\n\n"
                f"Use /download `{filename}` to get direct download link."
            )
        
    except Exception as e:
        await message.reply_text(f"❌ File not found or error: {str(e)}")

@app.on_message(filters.command("list"))
async def list_files(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    try:
        user_prefix = get_user_folder(message.from_user.id) + "/"
        response = s3_client.list_objects_v2(
            Bucket=WASABI_BUCKET, 
            Prefix=user_prefix
        )
        
        if 'Contents' not in response:
            await message.reply_text("📁 No files found in your storage.")
            return
        
        files = [obj['Key'].replace(user_prefix, "") for obj in response['Contents']]
        files_list = "\n".join([f"• `{file}`" for file in files[:10]])
        
        if len(files) > 10:
            files_list += f"\n\n...and {len(files) - 10} more files"
        
        await message.reply_text(f"📁 **Your Files:**\n\n{files_list}")
    
    except Exception as e:
        logger.error(f"List files error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("delete"))
async def delete_file(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    if len(message.command) < 2:
        await message.reply_text("Usage: /delete <filename>")
        return

    file_name = " ".join(message.command[1:])
    user_file_name = f"{get_user_folder(message.from_user.id)}/{file_name}"
    
    try:
        # Delete file from Wasabi
        s3_client.delete_object(
            Bucket=WASABI_BUCKET,
            Key=user_file_name
        )
        
        await message.reply_text(f"✅ Deleted: `{file_name}`")
    
    except Exception as e:
        logger.error(f"Delete error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("mystatus"))
async def my_status_command(client, message: Message):
    user_plan = premium_manager.get_user_plan(message.from_user.id)
    
    if user_plan:
        end_date = datetime.strptime(user_plan['end_date'], '%Y-%m-%d %H:%M:%S')
        days_left = (end_date - datetime.now()).days
        
        status_text = (
            f"🌟 **Premium Account Status**\n\n"
            f"📋 Plan: {user_plan['plan_type'].title()}\n"
            f"💾 Storage: {user_plan['storage_gb']}GB\n"
            f"📁 Max File Size: {user_plan['max_file_size_gb']}GB\n"
            f"📅 Expires: {user_plan['end_date'][:10]}\n"
            f"⏳ Days Left: {days_left}\n\n"
            f"Thank you for being a premium user! ✨"
        )
    else:
        status_text = (
            "⚡ **Free Account Status**\n\n"
            "💾 Storage: Unlimited (fair use)\n"
            "📁 Max File Size: 2GB\n"
            "🚀 Basic Support\n\n"
            "Use /premium to upgrade for more features!"
        )
    
    await message.reply_text(status_text)

# -----------------------------
# Flask Server Startup
# -----------------------------
print("Starting Flask server on port 8000...")
Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    print("🚀 Starting Wasabi Storage Bot...")
    print("✅ Bot is ready! Send files to upload.")
    app.run()
