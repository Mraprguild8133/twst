import os
import time
import json 
import math
import asyncio
import logging
import base64
import requests
from functools import wraps
from urllib.parse import quote
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask, render_template, request, jsonify

# Import configuration
from config import config

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use configuration from config module
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
ADMIN_IDS = config.ADMIN_IDS
WASABI_ACCESS_KEY = config.WASABI_ACCESS_KEY
WASABI_SECRET_KEY = config.WASABI_SECRET_KEY
WASABI_BUCKET = config.WASABI_BUCKET
WASABI_REGION = config.WASABI_REGION
MAX_FILE_SIZE = config.MAX_FILE_SIZE
CHUNK_SIZE = config.CHUNK_SIZE

# Payment Configuration (Add to your .env)
UPI_ID = os.getenv("UPI_ID", "your-upi-id@okaxis")
UPI_NAME = os.getenv("UPI_NAME", "Your Name")
SUBSCRIPTION_PRICE = int(os.getenv("SUBSCRIPTION_PRICE", "100"))
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
CURRENCY = "INR"

# GPLinks Configuration
GPLINKS_API_KEY = os.getenv("GPLINKS_API_KEY", "")
GPLINKS_API_URL = "https://gplinks.in/api"
AUTO_SHORTEN = os.getenv("AUTO_SHORTEN", "true").lower() == "true"

# Player URL configuration
RENDER_URL = os.getenv("RENDER_URL", "http://localhost:8000")
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpeg', '.mpg'}

# In-memory storage for authorized user IDs
ALLOWED_USERS = set(ADMIN_IDS)

# User payment data storage
USER_PAYMENTS_FILE = "user_payments.json"
user_payments = {}

# Pending payments storage
PENDING_PAYMENTS_FILE = "pending_payments.json"
pending_payments = {}

# Performance optimization settings
MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)
BUFFER_SIZE = 256 * 1024

# Thread pool for parallel operations
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# --- Payment Management System ---
def load_user_payments():
    """Load user payment data from file"""
    global user_payments
    try:
        if os.path.exists(USER_PAYMENTS_FILE):
            with open(USER_PAYMENTS_FILE, 'r') as f:
                user_payments = json.load(f)
            logger.info(f"✅ Loaded {len(user_payments)} user payments")
    except Exception as e:
        logger.error(f"❌ Failed to load user payments: {e}")
        user_payments = {}

def load_pending_payments():
    """Load pending payments data from file"""
    global pending_payments
    try:
        if os.path.exists(PENDING_PAYMENTS_FILE):
            with open(PENDING_PAYMENTS_FILE, 'r') as f:
                pending_payments = json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load pending payments: {e}")
        pending_payments = {}

def save_user_payments():
    """Save user payment data to file"""
    try:
        with open(USER_PAYMENTS_FILE, 'w') as f:
            json.dump(user_payments, f, indent=2)
    except Exception as e:
        logger.error(f"❌ Failed to save user payments: {e}")

def save_pending_payments():
    """Save pending payments data to file"""
    try:
        with open(PENDING_PAYMENTS_FILE, 'w') as f:
            json.dump(pending_payments, f, indent=2)
    except Exception as e:
        logger.error(f"❌ Failed to save pending payments: {e}")

def is_user_premium(user_id):
    """Check if user has active premium subscription"""
    if user_id in ADMIN_IDS:
        return True
    
    user_data = user_payments.get(str(user_id))
    if not user_data:
        return False
    
    expiry_date = datetime.fromisoformat(user_data['expiry_date'])
    return datetime.now() < expiry_date

def add_premium_user(user_id, days=SUBSCRIPTION_DAYS):
    """Add user to premium subscription"""
    expiry_date = datetime.now() + timedelta(days=days)
    user_payments[str(user_id)] = {
        'user_id': user_id,
        'purchase_date': datetime.now().isoformat(),
        'expiry_date': expiry_date.isoformat(),
        'plan_days': days,
        'status': 'active'
    }
    ALLOWED_USERS.add(user_id)
    save_user_payments()
    logger.info(f"✅ Added premium user: {user_id} for {days} days")

def remove_premium_user(user_id):
    """Remove user from premium subscription"""
    if str(user_id) in user_payments:
        del user_payments[str(user_id)]
    if user_id in ALLOWED_USERS and user_id not in ADMIN_IDS:
        ALLOWED_USERS.remove(user_id)
    save_user_payments()
    logger.info(f"🗑 Removed premium user: {user_id}")

# Load payments on startup
load_user_payments()
load_pending_payments()

# --- UPI Payment Manager ---
class UPIPaymentManager:
    def __init__(self):
        self.upi_id = UPI_ID
        self.upi_name = UPI_NAME
        self.price = SUBSCRIPTION_PRICE
        
    def generate_upi_url(self, user_id):
        """Generate UPI payment URL"""
        transaction_id = f"BOT{int(time.time())}{user_id}"
        amount = str(self.price)
        
        upi_url = f"upi://pay?pa={self.upi_id}&pn={self.upi_name}&am={amount}&tid={transaction_id}&tn=Premium%20Subscription&cu=INR"
        
        return {
            'transaction_id': transaction_id,
            'upi_url': upi_url,
            'amount': amount,
            'instructions': self.get_payment_instructions()
        }
    
    def get_payment_instructions(self):
        """Get payment instructions"""
        return (
            f"**Payment Instructions:**\n\n"
            f"1. **Open GPay/PhonePe/Any UPI App**\n"
            f"2. **Send ₹{self.price} to UPI ID:** `{self.upi_id}`\n"
            f"3. **Add Note:** Premium Subscription\n"
            f"4. **After payment, click '✅ I've Paid'**\n"
            f"5. **Forward payment screenshot to admin for verification**\n\n"
            f"**UPI ID:** `{self.upi_id}`\n"
            f"**Amount:** ₹{self.price}\n"
            f"**Name:** {self.upi_name}"
        )
    
    def store_pending_payment(self, user_id, transaction_id):
        """Store pending payment for verification"""
        pending_payments[transaction_id] = {
            'user_id': user_id,
            'transaction_id': transaction_id,
            'amount': self.price,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        save_pending_payments()
    
    def verify_payment(self, transaction_id):
        """Verify payment (manual verification by admin)"""
        if transaction_id in pending_payments:
            payment_data = pending_payments[transaction_id]
            user_id = payment_data['user_id']
            
            # Add user to premium
            add_premium_user(user_id, SUBSCRIPTION_DAYS)
            
            # Remove from pending
            del pending_payments[transaction_id]
            save_pending_payments()
            
            return True
        return False

# Initialize payment manager
payment_manager = UPIPaymentManager()

# --- GPLinks.in Shortener Functions ---
async def shorten_url_gplinks(long_url):
    """Shorten URL using GPLinks.in API"""
    if not GPLINKS_API_KEY or not AUTO_SHORTEN:
        return long_url
    
    try:
        api_url = f"{GPLINKS_API_URL}?api={GPLINKS_API_KEY}&url={quote(long_url)}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                shortened_url = data.get('shortenedUrl')
                if shortened_url:
                    logger.info(f"✅ URL shortened: {long_url} -> {shortened_url}")
                    return shortened_url
            else:
                logger.warning(f"GPLinks API error: {data.get('message', 'Unknown error')}")
        else:
            logger.warning(f"GPLinks API HTTP error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"GPLinks shortening failed: {e}")
    
    return long_url

async def shorten_all_urls(direct_url, player_url):
    """Shorten both direct and player URLs"""
    shortened_direct = await shorten_url_gplinks(direct_url) if direct_url else None
    shortened_player = await shorten_url_gplinks(player_url) if player_url else None
    
    return shortened_direct, shortened_player

# --- Callback Data Management ---
class CallbackData:
    def __init__(self):
        self.file_map = {}
        self.next_id = 1
        self.payment_map = {}
    
    def store_file(self, filename):
        short_id = str(self.next_id)
        self.file_map[short_id] = filename
        self.next_id += 1
        if len(self.file_map) > 1000:
            self.file_map.clear()
            self.next_id = 1
        return short_id
    
    def get_file(self, short_id):
        return self.file_map.get(short_id)
    
    def clear_file(self, short_id):
        if short_id in self.file_map:
            del self.file_map[short_id]
    
    def store_payment(self, user_id, payment_data):
        self.payment_map[str(user_id)] = payment_data
    
    def get_payment(self, user_id):
        return self.payment_map.get(str(user_id))

# Global callback data manager
callback_data = CallbackData()

# --- Bot & Wasabi Client Initialization ---
app = Client("wasabi_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Optimized Boto3 S3 client for Wasabi
try:
    session = boto3.Session(
        aws_access_key_id=WASABI_ACCESS_KEY,
        aws_secret_access_key=WASABI_SECRET_KEY,
        region_name=WASABI_REGION
    )
    
    s3_client = session.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        config=boto3.session.Config(
            max_pool_connections=MAX_WORKERS,
            retries={'max_attempts': 5, 'mode': 'adaptive'},
            s3={'addressing_style': 'virtual'},
            read_timeout=300,
            connect_timeout=30
        )
    )
    
    s3_client.head_bucket(Bucket=WASABI_BUCKET)
    logger.info(f"✅ Successfully connected to Wasabi with {MAX_WORKERS} workers")
except Exception as e:
    logger.error(f"❌ Failed to connect to Wasabi: {e}")
    s3_client = None

# --- Performance Tracking ---
class TransferStats:
    def __init__(self):
        self.start_time = None
        self.bytes_transferred = 0
        self.last_update = 0
        
    def start(self):
        self.start_time = time.time()
        self.bytes_transferred = 0
        self.last_update = self.start_time
        
    def update(self, bytes_count):
        self.bytes_transferred += bytes_count
        self.last_update = time.time()
        
    def get_speed(self):
        if not self.start_time:
            return "0 B/s"
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return "0 B/s"
        speed = self.bytes_transferred / elapsed
        return self.human_speed(speed)
    
    def human_speed(self, speed):
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024.0:
                return f"{speed:.2f} {unit}"
            speed /= 1024.0
        return f"{speed:.2f} TB/s"

# Global stats tracker
transfer_stats = TransferStats()

# --- Helpers & Decorators ---
def is_admin(func):
    @wraps(func)
    async def wrapper(client, message):
        if message.from_user.id in ADMIN_IDS:
            await func(client, message)
        else:
            await message.reply_text("⛔️ Access denied. This command is for admin only.")
    return wrapper

def is_authorized(func):
    @wraps(func)
    async def wrapper(client, message):
        user_id = message.from_user.id
        if user_id in ALLOWED_USERS or is_user_premium(user_id):
            await func(client, message)
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy Subscription", callback_data="buy_subscription")],
                [InlineKeyboardButton("ℹ️ Pricing Info", callback_data="pricing_info")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
            await message.reply_text(
                "🔒 **Premium Feature**\n\n"
                "You need an active subscription to use this bot.\n\n"
                f"**Price:** ₹{SUBSCRIPTION_PRICE} for {SUBSCRIPTION_DAYS} days\n"
                "**Features:**\n"
                "• Unlimited file uploads\n"
                "• High-speed transfers\n"
                "• Video streaming player\n"
                "• Direct download links\n"
                "• 24/7 support",
                reply_markup=keyboard
            )
    return wrapper

def humanbytes(size):
    if not size:
        return "0B"
    size = int(size)
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()

def is_video_file(filename):
    return get_file_extension(filename) in SUPPORTED_VIDEO_FORMATS

def get_file_type(filename):
    ext = get_file_extension(filename)
    if ext in SUPPORTED_VIDEO_FORMATS:
        return 'video'
    return 'other'

def generate_player_url(filename, presigned_url):
    if not RENDER_URL:
        return None
    file_type = get_file_type(filename)
    if file_type == 'video':
        encoded_url = base64.urlsafe_b64encode(presigned_url.encode()).decode().rstrip('=')
        return f"{RENDER_URL}/player/{file_type}/{encoded_url}"
    return None

async def create_link_buttons(direct_url, player_url, filename):
    buttons = []
    
    file_id = callback_data.store_file(filename)
    
    shortened_direct, shortened_player = await shorten_all_urls(direct_url, player_url)
    
    display_direct = shortened_direct if shortened_direct and shortened_direct != direct_url else direct_url
    display_player = shortened_player if shortened_player and shortened_player != player_url else player_url
    
    if display_direct:
        buttons.append([InlineKeyboardButton("📥 Direct Download", url=display_direct)])
    
    if display_player:
        buttons.append([InlineKeyboardButton("🎥 Stream Video", url=display_player)])
    
    if direct_url:
        buttons.append([
            InlineKeyboardButton("📋 Copy Direct", callback_data=f"cd_{file_id}"),
            InlineKeyboardButton("📋 Copy Player", callback_data=f"cp_{file_id}")
        ])
    
    buttons.append([
        InlineKeyboardButton("🗑 Delete File", callback_data=f"del_{file_id}"),
        InlineKeyboardButton("🔄 New Links", callback_data=f"ref_{file_id}")
    ])
    
    return InlineKeyboardMarkup(buttons)

async def create_simple_buttons(direct_url, player_url, filename):
    buttons = []
    
    file_id = callback_data.store_file(filename)
    
    shortened_direct, shortened_player = await shorten_all_urls(direct_url, player_url)
    
    display_direct = shortened_direct if shortened_direct and shortened_direct != direct_url else direct_url
    display_player = shortened_player if shortened_player and shortened_player != player_url else player_url
    
    if display_direct:
        buttons.append([InlineKeyboardButton("📥 Direct Download", url=display_direct)])
    
    if display_player:
        buttons.append([InlineKeyboardButton("🎥 Stream Video", url=display_player)])
    
    if direct_url:
        buttons.append([
            InlineKeyboardButton("📋 Copy Direct", callback_data=f"cd_{file_id}"),
            InlineKeyboardButton("📋 Copy Player", callback_data=f"cp_{file_id}")
        ])
    
    return InlineKeyboardMarkup(buttons)

# --- Progress Callback ---
last_update_time = {}
progress_cache = {}

async def progress_callback(current, total, message, status, operation_type="download"):
    chat_id = message.chat.id
    message_id = message.id
    
    if operation_type == "download":
        transfer_stats.update(current - progress_cache.get(message_id, 0))
    
    progress_cache[message_id] = current
    
    now = time.time()
    if (now - last_update_time.get(message_id, 0)) < 1.0 and current != total:
        return
    
    last_update_time[message_id] = now

    percentage = current * 100 / total
    progress_bar = "[{0}{1}]".format(
        '█' * int(percentage / 5),
        '░' * (20 - int(percentage / 5))
    )
    
    speed = transfer_stats.get_speed()
    
    details = (
        f"**{status}** 🚀\n"
        f"`{progress_bar}`\n"
        f"**Progress:** {percentage:.2f}%\n"
        f"**Speed:** {speed}\n"
        f"**Done:** {humanbytes(current)} / {humanbytes(total)}"
    )
    
    try:
        await app.edit_message_text(chat_id, message_id, text=details)
    except Exception as e:
        logger.debug(f"Progress update skipped: {e}")

# --- S3 Operations ---
async def upload_to_wasabi_parallel(file_path, file_name, status_message):
    try:
        file_size = os.path.getsize(file_path)
        
        if file_size > 50 * 1024 * 1024:
            return await upload_multipart(file_path, file_name, file_size, status_message)
        else:
            return await upload_single(file_path, file_name, file_size, status_message)
            
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise e

async def upload_multipart(file_path, file_name, file_size, status_message):
    try:
        mpu = s3_client.create_multipart_upload(
            Bucket=WASABI_BUCKET,
            Key=file_name,
            ContentType='application/octet-stream'
        )
        mpu_id = mpu['UploadId']
        
        part_size = CHUNK_SIZE
        part_count = math.ceil(file_size / part_size)
        parts = []
        
        logger.info(f"Starting multipart upload: {part_count} parts")
        
        upload_tasks = []
        
        for part_num in range(1, part_count + 1):
            start = (part_num - 1) * part_size
            end = min(start + part_size, file_size)
            
            task = upload_part(
                file_path, file_name, mpu_id, part_num, start, end, status_message
            )
            upload_tasks.append(task)
        
        parts = await asyncio.gather(*upload_tasks)
        
        s3_client.complete_multipart_upload(
            Bucket=WASABI_BUCKET,
            Key=file_name,
            UploadId=mpu_id,
            MultipartUpload={'Parts': parts}
        )
        
        logger.info("Multipart upload completed successfully")
        return True
        
    except Exception as e:
        try:
            s3_client.abort_multipart_upload(
                Bucket=WASABI_BUCKET,
                Key=file_name,
                UploadId=mpu_id
            )
        except:
            pass
        raise e

async def upload_part(file_path, file_name, mpu_id, part_num, start, end, status_message):
    loop = asyncio.get_event_loop()
    
    def _upload_part():
        with open(file_path, 'rb') as f:
            f.seek(start)
            data = f.read(end - start)
            
            response = s3_client.upload_part(
                Bucket=WASABI_BUCKET,
                Key=file_name,
                PartNumber=part_num,
                UploadId=mpu_id,
                Body=data
            )
            
            return {'ETag': response['ETag'], 'PartNumber': part_num}
    
    return await loop.run_in_executor(thread_pool, _upload_part)

async def upload_single(file_path, file_name, file_size, status_message):
    loop = asyncio.get_event_loop()
    
    class ProgressTracker:
        def __init__(self):
            self.uploaded = 0
            self.file_size = file_size
        
        def __call__(self, bytes_amount):
            self.uploaded += bytes_amount
            asyncio.run_coroutine_threadsafe(
                progress_callback(
                    self.uploaded, 
                    self.file_size, 
                    status_message, 
                    "🚀 Uploading...",
                    "upload"
                ),
                loop
            )
    
    progress_tracker = ProgressTracker()
    
    await loop.run_in_executor(
        thread_pool,
        lambda: s3_client.upload_file(
            file_path,
            WASABI_BUCKET,
            file_name,
            Callback=progress_tracker
        )
    )
    return True

async def generate_presigned_url(file_name):
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': file_name},
            ExpiresIn=604800
        )
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None

# --- File Download ---
async def download_file_ultrafast(client, message, file_path, status_message):
    try:
        transfer_stats.start()
        progress_cache[status_message.id] = 0
        
        await client.download_media(
            message=message,
            file_name=file_path,
            progress=progress_callback,
            progress_args=(status_message, "⬇️ Downloading...", "download")
        )
        
        if status_message.id in progress_cache:
            del progress_cache[status_message.id]
            
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise e

# --- Payment Command Handlers ---
@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_premium = is_user_premium(user_id)
    
    if is_premium:
        premium_status = "✅ **Premium User**"
        user_data = user_payments.get(str(user_id))
        if user_data:
            expiry = datetime.fromisoformat(user_data['expiry_date'])
            days_left = (expiry - datetime.now()).days
            premium_status += f" ({days_left} days remaining)"
    else:
        premium_status = "❌ **Free User**"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Upload File", callback_data="upload_help")],
        [InlineKeyboardButton("💳 Buy Premium", callback_data="buy_subscription")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help_info"),
         InlineKeyboardButton("👤 My ID", callback_data="my_id")],
        [InlineKeyboardButton("🚀 Speed Test", callback_data="speed_test")]
    ])
    
    await message.reply_text(
        f"🚀 **Ultra-Fast Wasabi Upload Bot**\n\n"
        f"**Your User ID:** `{user_id}`\n"
        f"**Status:** {premium_status}\n\n"
        "**Features:**\n"
        "• ⚡ Instant transfer speeds\n"
        "• 🎥 Video streaming player\n"
        "• 📱 One-click download buttons\n"
        "• 🔗 7-day direct links\n"
        f"• 🔗 Auto URL shortening: {'✅ Enabled' if AUTO_SHORTEN and GPLINKS_API_KEY else '❌ Disabled'}\n\n"
        f"**{'✅ You can upload files!' if is_premium else '💳 Subscribe to upload files!'}**",
        reply_markup=keyboard
    )

@app.on_message(filters.command("buy"))
async def buy_handler(client: Client, message: Message):
    """Handle subscription purchases"""
    user_id = message.from_user.id
    
    if is_user_premium(user_id):
        await message.reply_text("✅ You already have an active subscription!")
        return
    
    # Create UPI payment
    payment_data = payment_manager.generate_upi_url(user_id)
    
    # Store payment data
    callback_data.store_payment(user_id, payment_data)
    payment_manager.store_pending_payment(user_id, payment_data['transaction_id'])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay via UPI", url=payment_data['upi_url'])],
        [InlineKeyboardButton("✅ I've Paid", callback_data="confirm_payment")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/your_admin_username")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])
    
    await message.reply_text(
        f"💳 **Premium Subscription - UPI Payment**\n\n"
        f"**Price:** ₹{SUBSCRIPTION_PRICE}\n"
        f"**Duration:** {SUBSCRIPTION_DAYS} days\n"
        f"**Payment Method:** GPay/PhonePe/Any UPI App\n\n"
        f"{payment_data['instructions']}\n\n"
        f"**Transaction ID:** `{payment_data['transaction_id']}`\n"
        "After payment, click 'I've Paid' and forward the screenshot to admin.",
        reply_markup=keyboard
    )

@app.on_message(filters.command("myplan"))
async def myplan_handler(client: Client, message: Message):
    """Show user's current plan details"""
    user_id = message.from_user.id
    
    if is_user_premium(user_id):
        user_data = user_payments.get(str(user_id))
        expiry = datetime.fromisoformat(user_data['expiry_date'])
        purchase = datetime.fromisoformat(user_data['purchase_date'])
        days_left = (expiry - datetime.now()).days
        
        await message.reply_text(
            f"✅ **Active Premium Plan**\n\n"
            f"**Purchased:** {purchase.strftime('%Y-%m-%d')}\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d')}\n"
            f"**Days Left:** {days_left} days\n"
            f"**Plan:** {user_data['plan_days']} days subscription"
        )
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Subscription", callback_data="buy_subscription")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
        await message.reply_text(
            "❌ **No Active Subscription**\n\n"
            "You don't have an active premium subscription.\n"
            "Subscribe now to unlock all features!",
            reply_markup=keyboard
        )

# --- Enhanced Callback Query Handler ---
@app.on_callback_query()
async def handle_callback_query(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    message = callback_query.message
    
    try:
        if data == "buy_subscription":
            await callback_query.answer()
            await buy_handler(client, message)
            return
            
        elif data == "confirm_payment":
            payment_data = callback_data.get_payment(user_id)
            if not payment_data:
                await callback_query.answer("❌ No payment session found", show_alert=True)
                return
            
            await callback_query.answer("🔄 Payment verification pending...", show_alert=False)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/your_admin_username")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
            
            await message.edit_text(
                f"⏳ **Payment Verification**\n\n"
                f"**Transaction ID:** `{payment_data['transaction_id']}`\n"
                f"**Amount:** ₹{SUBSCRIPTION_PRICE}\n\n"
                "Your payment is being verified manually.\n"
                "Please forward the payment screenshot to admin for faster activation.\n\n"
                "You will be notified once your subscription is activated.",
                reply_markup=keyboard
            )
            return
            
        elif data == "pricing_info":
            await callback_query.answer()
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy Now", callback_data="buy_subscription")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
            await message.edit_text(
                f"💰 **Pricing Information**\n\n"
                f"**Basic Subscription:**\n"
                f"• Price: ₹{SUBSCRIPTION_PRICE}\n"
                f"• Duration: {SUBSCRIPTION_DAYS} days\n"
                f"• File Size: Up to 4GB\n"
                f"• Speed: Ultra-Fast\n"
                f"• Support: 24/7\n\n"
                f"**Features Included:**\n"
                "• Unlimited uploads\n"
                "• Video streaming\n"
                "• Direct downloads\n"
                "• URL shortening\n"
                "• Priority support",
                reply_markup=keyboard
            )
            return
        
        # Existing callback handlers for file operations
        if '_' not in data:
            await callback_query.answer("❌ Invalid button data", show_alert=False)
            return
            
        action, file_id = data.split('_', 1)
        filename = callback_data.get_file(file_id)
        
        if not filename:
            await callback_query.answer("❌ File data expired", show_alert=False)
            return
        
        logger.info(f"Callback: {action} for file: {filename}")
        
        if action == "cd":
            if not is_user_premium(user_id):
                await callback_query.answer("⛔️ Premium subscription required!", show_alert=True)
                return
                
            presigned_url = await generate_presigned_url(filename)
            
            if presigned_url:
                shortened_url = await shorten_url_gplinks(presigned_url)
                await callback_query.answer("📋 Direct link copied!", show_alert=False)
                await message.reply_text(
                    f"**Direct Download Link:**\n`{shortened_url}`",
                    reply_to_message_id=message.id
                )
            else:
                await callback_query.answer("❌ Failed to generate link", show_alert=True)
                
        elif action == "cp":
            if not is_user_premium(user_id):
                await callback_query.answer("⛔️ Premium subscription required!", show_alert=True)
                return
                
            presigned_url = await generate_presigned_url(filename)
            player_url = generate_player_url(filename, presigned_url) if presigned_url else None
            
            if player_url:
                shortened_player = await shorten_url_gplinks(player_url)
                await callback_query.answer("📋 Player link copied!", show_alert=False)
                await message.reply_text(
                    f"**Player URL:**\n{shortened_player}",
                    reply_to_message_id=message.id
                )
            else:
                await callback_query.answer("❌ Not a video file", show_alert=True)
                
        elif action == "del":
            if user_id not in ADMIN_IDS:
                await callback_query.answer("⛔️ Only admin can delete!", show_alert=True)
                return
                
            try:
                s3_client.delete_object(Bucket=WASABI_BUCKET, Key=filename)
                await callback_query.answer("✅ File deleted!", show_alert=True)
                await message.edit_text(
                    f"🗑 **File Deleted**\n\n`{filename}` has been removed from storage.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back to Bot", url=f"https://t.me/{client.me.username}")]
                    ])
                )
                callback_data.clear_file(file_id)
            except Exception as e:
                await callback_query.answer(f"❌ Delete failed", show_alert=True)
                
        elif action == "ref":
            if not is_user_premium(user_id):
                await callback_query.answer("⛔️ Premium subscription required!", show_alert=True)
                return
                
            await callback_query.answer("🔄 Generating fresh links...")
            
            presigned_url = await generate_presigned_url(filename)
            player_url = generate_player_url(filename, presigned_url) if is_video_file(filename) else None
            
            if presigned_url:
                if user_id in ADMIN_IDS:
                    keyboard = await create_link_buttons(presigned_url, player_url, filename)
                else:
                    keyboard = await create_simple_buttons(presigned_url, player_url, filename)
                
                await message.edit_reply_markup(reply_markup=keyboard)
                await callback_query.answer("✅ Links refreshed!", show_alert=False)
            else:
                await callback_query.answer("❌ Failed to refresh links", show_alert=True)
                
        else:
            await callback_query.answer("❌ Unknown action", show_alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback_query.answer("❌ An error occurred", show_alert=True)

# --- Admin Payment Management ---
@app.on_message(filters.command("verifypayment"))
@is_admin
async def verify_payment_handler(client: Client, message: Message):
    """Verify payment manually"""
    try:
        transaction_id = message.text.split()[1]
        
        if payment_manager.verify_payment(transaction_id):
            await message.reply_text(f"✅ Payment verified for transaction: `{transaction_id}`")
        else:
            await message.reply_text(f"❌ Transaction not found: `{transaction_id}`")
            
    except IndexError:
        await message.reply_text("⚠️ **Usage:** /verifypayment <transaction_id>")

@app.on_message(filters.command("addpremium"))
@is_admin
async def add_premium_handler(client: Client, message: Message):
    """Manually add premium subscription to user"""
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.reply_text("⚠️ **Usage:** /addpremium <user_id> <days>")
            return
            
        user_id = int(args[1])
        days = int(args[2])
        
        add_premium_user(user_id, days)
        
        await message.reply_text(
            f"✅ Added premium subscription to user `{user_id}` for {days} days."
        )
        
    except (IndexError, ValueError):
        await message.reply_text("❌ Invalid arguments. Usage: /addpremium <user_id> <days>")

@app.on_message(filters.command("removepremium"))
@is_admin
async def remove_premium_handler(client: Client, message: Message):
    """Remove user's premium subscription"""
    try:
        user_id = int(message.text.split()[1])
        remove_premium_user(user_id)
        
        await message.reply_text(f"🗑 Removed premium subscription from user `{user_id}`")
        
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** /removepremium <user_id>")

@app.on_message(filters.command("premiumusers"))
@is_admin
async def premium_users_handler(client: Client, message: Message):
    """List all premium users"""
    if not user_payments:
        await message.reply_text("📭 No premium users found.")
        return
    
    user_list = []
    for user_id, data in user_payments.items():
        expiry = datetime.fromisoformat(data['expiry_date'])
        days_left = (expiry - datetime.now()).days
        status = "✅ Active" if days_left > 0 else "❌ Expired"
        user_list.append(f"• `{user_id}` - {days_left} days left - {status}")
    
    users_text = "\n".join(user_list)
    
    await message.reply_text(
        f"👥 **Premium Users** ({len(user_list)})\n\n{users_text}"
    )

@app.on_message(filters.command("pendingpayments"))
@is_admin
async def pending_payments_handler(client: Client, message: Message):
    """List pending payments"""
    if not pending_payments:
        await message.reply_text("📭 No pending payments.")
        return
    
    payment_list = []
    for transaction_id, data in pending_payments.items():
        timestamp = datetime.fromisoformat(data['timestamp'])
        time_ago = datetime.now() - timestamp
        payment_list.append(f"• `{transaction_id}` - User: `{data['user_id']}` - {int(time_ago.total_seconds() / 60)} min ago")
    
    payments_text = "\n".join(payment_list)
    
    await message.reply_text(
        f"⏳ **Pending Payments** ({len(payment_list)})\n\n{payments_text}"
    )

# --- File Handler ---
@app.on_message(filters.document | filters.video | filters.audio)
@is_authorized
async def file_handler(client: Client, message: Message):
    if not s3_client:
        await message.reply_text("❌ **Error:** Wasabi client is not initialized.")
        return

    media = message.document or message.video or message.audio
    file_name = media.file_name
    file_size = media.file_size
    
    if file_size > MAX_FILE_SIZE:
        await message.reply_text(f"❌ **Error:** File is larger than {humanbytes(MAX_FILE_SIZE)}.")
        return

    status_message = await message.reply_text("🚀 Starting ultra-fast transfer...")
    
    # Create unique file path
    timestamp = int(time.time())
    safe_filename = f"{timestamp}_{file_name}"
    file_path = f"./downloads/{safe_filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        # 1. Ultra-fast download from Telegram
        await download_file_ultrafast(client, message, file_path, status_message)
        await status_message.edit_text("✅ Download complete. Starting instant upload...")

        # 2. Ultra-fast upload to Wasabi
        await upload_to_wasabi_parallel(file_path, safe_filename, status_message)
        
        # Show shortening status if enabled
        if AUTO_SHORTEN and GPLINKS_API_KEY:
            await status_message.edit_text("✅ Upload complete! Shortening URLs...")
        else:
            await status_message.edit_text("✅ Upload complete! Generating links...")
        
        # 3. Generate URLs
        presigned_url = await generate_presigned_url(safe_filename)
        player_url = generate_player_url(safe_filename, presigned_url) if is_video_file(file_name) else None
        
        # 4. Create buttons based on user role
        if message.from_user.id in ADMIN_IDS:
            keyboard = await create_link_buttons(presigned_url, player_url, safe_filename)
        else:
            keyboard = await create_simple_buttons(presigned_url, player_url, safe_filename)
        
        # 5. Prepare final message
        shortener_status = "🔗 URLs Auto-Shortened" if AUTO_SHORTEN and GPLINKS_API_KEY else "🔗 Direct URLs"
        
        final_message = (
            f"✅ **File Uploaded Successfully!** ⚡\n\n"
            f"**File:** `{file_name}`\n"
            f"**Size:** {humanbytes(file_size)}\n"
            f"**Stored as:** `{safe_filename}`\n"
            f"**URLs:** {shortener_status}\n\n"
            f"**Links valid for 7 days**"
        )
        
        await status_message.edit_text(final_message, reply_markup=keyboard, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Transfer failed: {e}")
        await status_message.edit_text(f"❌ **Transfer failed:** {str(e)}")
    finally:
        # Cleanup local file
        if os.path.exists(file_path):
            os.remove(file_path)

# --- Flask Web Server for Player ---
web_app = Flask(__name__)

@web_app.route('/')
def index():
    return render_template('index.html', render_url=RENDER_URL)

@web_app.route('/player/<file_type>/<encoded_url>')
def player(file_type, encoded_url):
    try:
        # Decode the URL
        padding = 4 - (len(encoded_url) % 4)
        encoded_url += '=' * padding
        video_url = base64.urlsafe_b64decode(encoded_url).decode()
        
        return render_template('player.html', 
                             video_url=video_url, 
                             file_type=file_type,
                             render_url=RENDER_URL)
    except Exception as e:
        return f"Error: {str(e)}", 400

@web_app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "wasabi_bot_player"})

def run_flask():
    web_app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)

# --- Main Function ---
if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("./downloads", exist_ok=True)
    
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🚀 Flask server started on port 8000")
    
    # Start the bot
    logger.info("🤖 Starting Ultra-Fast Wasabi Bot...")
    app.run()