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
from pyrogram.errors import FloodWait
from dotenv import load_dotenv
import logging
from collections import defaultdict
from datetime import datetime, timedelta
import botocore

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
MERCHANT_UPI_ID = os.getenv("MERCHANT_UPI_ID")  # your upi id like: username@okaxis
MERCHANT_NAME = os.getenv("MERCHANT_NAME", "Cloud Storage Pro")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "123456789"))  # Your Telegram user ID

# Premium plans configuration
PREMIUM_PLANS = {
    "basic": {
        "name": "Basic Plan",
        "price": 299,  # ₹299
        "storage_gb": 50,
        "max_file_size_gb": 4,
        "duration_days": 30,
        "features": ["50GB Storage", "4GB File Size", "Priority Support"]
    },
    "pro": {
        "name": "Pro Plan", 
        "price": 799,  # ₹799
        "storage_gb": 200,
        "max_file_size_gb": 10,
        "duration_days": 30,
        "features": ["200GB Storage", "10GB File Size", "24/7 Priority Support"]
    },
    "annual_pro": {
        "name": "Annual Pro",
        "price": 7999,  # ₹7,999
        "storage_gb": 200,
        "max_file_size_gb": 10,
        "duration_days": 365,
        "features": ["200GB Storage", "10GB File Size", "24/7 Priority Support", "2 Months Free"]
    }
}

# Validate environment variables
missing_vars = []
for var_name, var_value in [
    ("API_ID", API_ID),
    ("API_HASH", API_HASH),
    ("BOT_TOKEN", BOT_TOKEN),
    ("WASABI_ACCESS_KEY", WASABI_ACCESS_KEY),
    ("WASABI_SECRET_KEY", WASASBI_SECRET_KEY),
    ("WASABI_BUCKET", WASABI_BUCKET),
    ("MERCHANT_UPI_ID", MERCHANT_UPI_ID)
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
    
    s3_client.head_bucket(Bucket=WASABI_BUCKET)
    logger.info("Successfully connected to Wasabi bucket")
    
except Exception as e:
    logger.error(f"Wasabi connection failed: {e}")
    try:
        wasabi_endpoint_url = f'https://{WASABI_BUCKET}.s3.{WASABI_REGION}.wasabisys.com'
        s3_client = boto3.client(
            's3',
            endpoint_url=wasabi_endpoint_url,
            aws_access_key_id=WASABI_ACCESS_KEY,
            aws_secret_access_key=WASABI_SECRET_KEY,
            region_name=WASABI_REGION
        )
        s3_client.head_bucket(Bucket=WASABI_BUCKET)
        logger.info("Successfully connected to Wasabi bucket with alternative endpoint")
    except Exception as alt_e:
        logger.error(f"Alternative connection also failed: {alt_e}")
        raise Exception(f"Could not connect to Wasabi: {alt_e}")

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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS payment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    upi_transaction_id TEXT,
                    screenshot_file_id TEXT,
                    status TEXT DEFAULT 'pending',
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_date TIMESTAMP,
                    admin_notes TEXT
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
    
    def add_premium_user(self, user_id, plan_type, duration_days):
        plan = PREMIUM_PLANS[plan_type]
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO premium_users 
                (user_id, plan_type, start_date, end_date, storage_gb, max_file_size_gb, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, plan_type, start_date, end_date, plan['storage_gb'], plan['max_file_size_gb']))
    
    def get_user_plan(self, user_id):
        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM premium_users 
                WHERE user_id = ? AND is_active = 1 AND end_date > datetime('now')
            ''', (user_id,)).fetchone()
            return dict(row) if row else None
    
    def is_premium_user(self, user_id):
        return self.get_user_plan(user_id) is not None
    
    def create_payment_request(self, user_id, plan_type, amount, upi_transaction_id=None, screenshot_file_id=None):
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO payment_requests 
                (user_id, plan_type, amount, upi_transaction_id, screenshot_file_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, plan_type, amount, upi_transaction_id, screenshot_file_id))
            return cursor.lastrowid
    
    def get_pending_requests(self):
        with self.get_connection() as conn:
            return conn.execute('''
                SELECT pr.*, u.first_name, u.username 
                FROM payment_requests pr
                LEFT JOIN (SELECT DISTINCT user_id, first_name, username FROM payment_requests) u 
                ON pr.user_id = u.user_id
                WHERE pr.status = 'pending'
                ORDER BY pr.request_date DESC
            ''').fetchall()
    
    def update_payment_status(self, request_id, status, admin_notes=None):
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE payment_requests 
                SET status = ?, admin_notes = ?, approved_date = datetime('now')
                WHERE id = ?
            ''', (status, admin_notes, request_id))

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

@flask_app.route("/about")
def about():
    return render_template("about.html")

@flask_app.route("/premium")
def premium():
    return render_template("premium.html", plans=PREMIUM_PLANS, upi_id=MERCHANT_UPI_ID)

def run_flask():
    flask_app.run(host="0.0.0.0", port=8000, debug=False)

# -----------------------------
# Helper Functions
# -----------------------------
MEDIA_EXTENSIONS = {
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'],
    'audio': ['.mp3', '.m4a', '.ogg', '.wav', '.flac'],
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
}

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    for file_type, extensions in MEDIA_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return 'other'

def generate_player_url(filename, presigned_url):
    if not RENDER_URL:
        return None
    file_type = get_file_type(filename)
    if file_type in ['video', 'audio', 'image']:
        encoded_url = base64.urlsafe_b64encode(presigned_url.encode()).decode().rstrip('=')
        return f"{RENDER_URL}/player/{file_type}/{encoded_url}"
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
    keyboard = []
    if player_url:
        keyboard.append([InlineKeyboardButton("🎬 Web Player", url=player_url)])
    keyboard.append([InlineKeyboardButton("📥 Direct Download", url=presigned_url)])
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
# Payment Helper Functions
# -----------------------------
def create_premium_plans_keyboard():
    keyboard = []
    for plan_id, plan in PREMIUM_PLANS.items():
        button_text = f"{plan['name']} - ₹{plan['price']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"premium_{plan_id}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_premium")])
    return InlineKeyboardMarkup(keyboard)

def create_payment_confirmation_keyboard(plan_id):
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_payment_{plan_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_admin_actions_keyboard(request_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{request_id}")
        ],
        [InlineKeyboardButton("📝 Add Notes", callback_data=f"notes_{request_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# -----------------------------
# Bot Handlers
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
        "<b>⚡ Extreme Performance Features:</b>\n"
        "• 2GB file size support (Free)\n"
        "• Up to 10GB file size (Premium)\n"
        "• Real-time speed monitoring\n"
        "• Memory optimization\n\n"
        "<b>💎 Owner:</b> Mraprguild\n"
        "<b>📧 Email:</b> mraprguild@gmail.com\n"
        "<b>📱 Telegram:</b> @Sathishkumar33"
    )

@app.on_message(filters.command("premium"))
async def premium_command(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
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
            f"⏳ Days Left: {days_left}\n\n"
            "You can still browse available plans below:"
        )
    
    plans_text = "💎 **Premium Plans Available:**\n\n"
    for plan_id, plan in PREMIUM_PLANS.items():
        plans_text += f"**{plan['name']}** - ₹{plan['price']}\n"
        plans_text += f"• {plan['storage_gb']}GB Storage\n"
        plans_text += f"• {plan['max_file_size_gb']}GB Max File Size\n"
        plans_text += f"• {plan['duration_days']} Days Access\n"
        for feature in plan['features']:
            plans_text += f"• {feature}\n"
        plans_text += "\n"
    
    plans_text += f"**Payment Method:**\nGPay UPI: `{MERCHANT_UPI_ID}`\n\nClick a plan below to proceed:"
    
    await message.reply_text(
        plans_text,
        reply_markup=create_premium_plans_keyboard()
    )

@app.on_callback_query(filters.regex("^premium_"))
async def handle_premium_selection(client, callback_query):
    plan_id = callback_query.data.replace("premium_", "")
    
    if plan_id not in PREMIUM_PLANS:
        await callback_query.answer("Invalid plan selected", show_alert=True)
        return
    
    plan = PREMIUM_PLANS[plan_id]
    
    payment_instructions = (
        f"💎 **{plan['name']}** - ₹{plan['price']}\n\n"
        f"**Payment Instructions:**\n"
        f"1. Open Google Pay app\n"
        f"2. Send ₹{plan['price']} to UPI ID:\n"
        f"   `{MERCHANT_UPI_ID}`\n"
        f"3. **Important:** Add note: `{callback_query.from_user.id}_{plan_id}`\n"
        f"4. Take screenshot of payment success\n"
        f"5. Click 'Confirm Payment' below\n"
        f"6. Send the screenshot when asked\n\n"
        f"**After payment, your account will be activated within 1-2 hours.**\n\n"
        f"Click 'Confirm Payment' when ready:"
    )
    
    await callback_query.message.edit_text(
        payment_instructions,
        reply_markup=create_payment_confirmation_keyboard(plan_id)
    )

@app.on_callback_query(filters.regex("^confirm_payment_"))
async def handle_payment_confirmation(client, callback_query):
    plan_id = callback_query.data.replace("confirm_payment_", "")
    user_id = callback_query.from_user.id
    
    if plan_id not in PREMIUM_PLANS:
        await callback_query.answer("Invalid plan selected", show_alert=True)
        return
    
    plan = PREMIUM_PLANS[plan_id]
    
    # Create payment request
    request_id = premium_manager.create_payment_request(
        user_id=user_id,
        plan_type=plan_id,
        amount=plan['price']
    )
    
    await callback_query.message.edit_text(
        f"✅ **Payment Request Created**\n\n"
        f"📋 Plan: {plan['name']}\n"
        f"💰 Amount: ₹{plan['price']}\n"
        f"🆔 Request ID: `{request_id}`\n\n"
        f"**Next Steps:**\n"
        f"1. Make payment to: `{MERCHANT_UPI_ID}`\n"
        f"2. **Add note:** `{user_id}_{plan_id}`\n"
        f"3. Send screenshot of payment success\n"
        f"4. We'll activate your account within 1-2 hours\n\n"
        f"**Send your payment screenshot now:**"
    )
    
    # Notify admin
    admin_text = (
        f"🆕 New Payment Request\n\n"
        f"👤 User: {callback_query.from_user.first_name} (@{callback_query.from_user.username})\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📋 Plan: {plan['name']}\n"
        f"💰 Amount: ₹{plan['price']}\n"
        f"🆔 Request ID: `{request_id}`\n\n"
        f"Waiting for payment screenshot..."
    )
    
    try:
        await client.send_message(
            ADMIN_USER_ID,
            admin_text,
            reply_markup=create_admin_actions_keyboard(request_id)
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

@app.on_message(filters.photo | filters.document)
async def handle_payment_screenshot(client, message: Message):
    # Check if user has pending payment request
    user_id = message.from_user.id
    
    # Simple check - if user recently used /premium command and sent a file
    # In production, you'd want a more robust state management
    
    if message.caption and ("payment" in message.caption.lower() or "screenshot" in message.caption.lower()):
        # This might be a payment screenshot
        pending_text = (
            "📸 Payment screenshot received!\n\n"
            "We've received your payment confirmation. "
            "Your account will be activated within 1-2 hours after verification.\n\n"
            "Thank you for your purchase! 💫"
        )
        await message.reply_text(pending_text)
        
        # Notify admin
        try:
            admin_text = f"📸 Payment screenshot received from user {user_id}"
            await client.forward_messages(ADMIN_USER_ID, message.chat.id, message.id)
            await client.send_message(ADMIN_USER_ID, admin_text)
        except Exception as e:
            logger.error(f"Failed to forward screenshot to admin: {e}")

@app.on_callback_query(filters.regex("^approve_"))
async def handle_approval(client, callback_query):
    if callback_query.from_user.id != ADMIN_USER_ID:
        await callback_query.answer("Only admin can perform this action", show_alert=True)
        return
    
    request_id = int(callback_query.data.replace("approve_", ""))
    
    # Get payment request details
    with premium_manager.get_connection() as conn:
        request = conn.execute(
            'SELECT * FROM payment_requests WHERE id = ?', 
            (request_id,)
        ).fetchone()
    
    if not request:
        await callback_query.answer("Request not found", show_alert=True)
        return
    
    # Activate premium for user
    plan = PREMIUM_PLANS[request['plan_type']]
    premium_manager.add_premium_user(
        user_id=request['user_id'],
        plan_type=request['plan_type'],
        duration_days=plan['duration_days']
    )
    
    # Update payment request status
    premium_manager.update_payment_status(request_id, "approved", "Payment verified and activated")
    
    # Notify user
    try:
        user_notification = (
            f"🎉 **Premium Account Activated!**\n\n"
            f"Your {plan['name']} has been successfully activated!\n"
            f"📅 Valid for: {plan['duration_days']} days\n"
            f"💾 Storage: {plan['storage_gb']}GB\n"
            f"📁 Max File Size: {plan['max_file_size_gb']}GB\n\n"
            f"Thank you for your purchase! Enjoy premium features. ✨"
        )
        await client.send_message(request['user_id'], user_notification)
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await callback_query.message.edit_text(
        f"✅ **Payment Approved**\n\n"
        f"👤 User ID: `{request['user_id']}`\n"
        f"📋 Plan: {plan['name']}\n"
        f"💰 Amount: ₹{request['amount']}\n"
        f"✅ Status: Activated\n\n"
        f"User has been notified."
    )
    
    await callback_query.answer("Payment approved and user activated")

@app.on_callback_query(filters.regex("^reject_"))
async def handle_rejection(client, callback_query):
    if callback_query.from_user.id != ADMIN_USER_ID:
        await callback_query.answer("Only admin can perform this action", show_alert=True)
        return
    
    request_id = int(callback_query.data.replace("reject_", ""))
    
    # Update payment request status
    premium_manager.update_payment_status(request_id, "rejected", "Payment rejected by admin")
    
    # Notify user
    try:
        user_notification = (
            "❌ **Payment Rejected**\n\n"
            "Your payment request has been rejected. "
            "If you believe this is an error, please contact support.\n\n"
            "Possible reasons:\n"
            "• Payment not received\n"
            "• Incorrect UPI note\n"
            "• Screenshot unclear\n\n"
            "Please try again or contact @Sathishkumar33 for help."
        )
        await client.send_message(request['user_id'], user_notification)
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await callback_query.message.edit_text(
        f"❌ **Payment Rejected**\n\n"
        f"🆔 Request ID: `{request_id}`\n"
        f"✅ Status: Rejected\n\n"
        f"User has been notified."
    )
    
    await callback_query.answer("Payment rejected")

@app.on_callback_query(filters.regex("^cancel_"))
async def handle_cancellation(client, callback_query):
    await callback_query.message.edit_text(
        "❌ Premium plan selection cancelled.\n\n"
        "You can use /premium anytime to view available plans."
    )

# Admin command to view pending requests
@app.on_message(filters.command("pending_payments") & filters.user(ADMIN_USER_ID))
async def pending_payments_command(client, message: Message):
    pending_requests = premium_manager.get_pending_requests()
    
    if not pending_requests:
        await message.reply_text("No pending payment requests.")
        return
    
    requests_text = "📋 **Pending Payment Requests:**\n\n"
    
    for req in pending_requests:
        requests_text += (
            f"🆔 **Request ID:** `{req['id']}`\n"
            f"👤 **User:** {req['first_name']} (@{req['username'] or 'N/A'})\n"
            f"🆔 **User ID:** `{req['user_id']}`\n"
            f"📋 **Plan:** {req['plan_type']}\n"
            f"💰 **Amount:** ₹{req['amount']}\n"
            f"📅 **Request Date:** {req['request_date']}\n"
            f"────────────────────\n"
        )
    
    await message.reply_text(requests_text)

# Modified upload handler with premium checks
@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def upload_file_handler(client, message: Message):
    if is_rate_limited(message.from_user.id):
        await message.reply_text("Too many requests. Please try again in a minute.")
        return
        
    media = message.document or message.video or message.audio or message.photo
    if not media:
        await message.reply_text("Unsupported file type")
        return

    # Get file size
    if message.photo:
        file_size = message.photo.sizes[-1].file_size
    else:
        file_size = media.file_size
    
    # Check file size limit with premium support
    max_allowed_size = get_max_file_size(message.from_user.id)
    if file_size > max_allowed_size:
        user_plan = premium_manager.get_user_plan(message.from_user.id)
        if user_plan:
            await message.reply_text(
                f"File too large. Your premium plan allows up to {user_plan['max_file_size_gb']}GB files. "
                f"Current file: {humanbytes(file_size)}"
            )
        else:
            await message.reply_text(
                f"File too large. Free users limited to {humanbytes(MAX_FILE_SIZE)}. "
                f"Use /premium to upgrade for larger files up to 10GB!"
            )
        return

    # Continue with existing upload logic...
    status_message = await message.reply_text("📥 Downloading...\n[○○○○○○○○○○○○] 0.0%\nProcessed: 0.00B of 0000MB\nSpeed: 0.00B/s | ETA: -\nElapsed: 00s\nUpload: Telegram\nDownload: Wasabi")

    download_start_time = time.time()
    last_update_time = time.time()
    processed_bytes = 0
    last_processed_bytes = 0
    start_time = time.time()

    async def progress_callback(current, total):
        nonlocal processed_bytes, last_update_time, last_processed_bytes
        processed_bytes = current
        current_time = time.time()
        
        if current_time - last_update_time >= 1:
            percentage = (current / total) * 100
            elapsed_time = current_time - start_time
            
            speed = (current - last_processed_bytes) / (current_time - last_update_time)
            
            if speed > 0:
                eta = (total - current) / speed
            else:
                eta = 0
            
            progress_bar = create_progress_bar(percentage)
            
            # Add premium badge if user has premium
            premium_badge = " 🌟" if premium_manager.is_premium_user(message.from_user.id) else ""
            
            progress_text = (
                f"📥 Downloading...{premium_badge}\n"
                f"[{progress_bar}] {percentage:.1f}%\n"
                f"Processed: {humanbytes(current)} of {humanbytes(total)}\n"
                f"Speed: {humanbytes(speed)}/s | ETA: {format_eta(eta)}\n"
                f"Elapsed: {format_elapsed(elapsed_time)}\n"
                f"Upload: Telegram\n"
                f"Download: Wasabi"
            )
            
            try:
                await status_message.edit_text(progress_text)
                last_update_time = current_time
                last_processed_bytes = current
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass

    try:
        file_path = await message.download(progress=progress_callback)
        file_name = sanitize_filename(os.path.basename(file_path))
        user_file_name = f"{get_user_folder(message.from_user.id)}/{file_name}"
        
        await status_message.edit_text("📤 Uploading to Wasabi...")
        
        await asyncio.to_thread(
            s3_client.upload_file,
            file_path,
            WASABI_BUCKET,
            user_file_name
        )
        
        presigned_url = s3_client.generate_presigned_url(
            'get_object', 
            Params={'Bucket': WASABI_BUCKET, 'Key': user_file_name}, 
            ExpiresIn=86400
        )
        
        player_url = generate_player_url(file_name, presigned_url)
        keyboard = create_download_keyboard(presigned_url, player_url)
        
        total_time = time.time() - start_time
        
        # Add premium status to completion message
        premium_status = " 🌟 Premium" if premium_manager.is_premium_user(message.from_user.id) else " ⚡ Free"
        
        response_text = (
            f"✅ Upload complete!{premium_status}\n\n"
            f"📁 File: {file_name}\n"
            f"📦 Size: {humanbytes(file_size)}\n"
            f"⏱️ Time: {format_elapsed(total_time)}\n"
            f"⏰ Link expires: 24 hours"
        )
        
        if player_url:
            response_text += f"\n\n🎬 Web Player: {player_url}"
        
        await status_message.edit_text(
            response_text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

# Add premium status command
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
            f"📅 Started: {user_plan['start_date']}\n"
            f"📅 Expires: {user_plan['end_date']}\n"
            f"⏳ Days Left: {days_left}\n\n"
            f"Thank you for being a premium user! ✨"
        )
    else:
        status_text = (
            "⚡ **Free Account Status**\n\n"
            "💾 Storage: Unlimited (with fair use)\n"
            "📁 Max File Size: 2GB\n"
            "🚀 Basic Support\n\n"
            "Use /premium to upgrade for more features!"
        )
    
    await message.reply_text(status_text)

# Keep existing handlers for download, play, list, delete (they don't need modification)
@app.on_message(filters.command("download"))
async def download_file_handler(client, message: Message):
    # ... existing download code ...
    pass

@app.on_message(filters.command("play"))
async def play_file(client, message: Message):
    # ... existing play code ...
    pass

@app.on_message(filters.command("list"))
async def list_files(client, message: Message):
    # ... existing list code ...
    pass

@app.on_message(filters.command("delete"))
async def delete_file(client, message: Message):
    # ... existing delete code ...
    pass

# -----------------------------
# Flask Server Startup
# -----------------------------
print("Starting Flask server on port 8000...")
Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    print("Starting Wasabi Storage Bot with Premium UPI Payments...")
    app.run()
