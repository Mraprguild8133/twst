import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardButton, 
    InlineKeyboardMarkup, CallbackQuery
)
from pyrogram.enums import ParseMode

from config import Config

# Initialize bot
app = Client(
    "wasabi_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Initialize Wasabi S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=Config.WASABI_ACCESS_KEY,
    aws_secret_access_key=Config.WASABI_SECRET_KEY,
    endpoint_url=Config.WASABI_ENDPOINT,
    region_name=Config.WASABI_REGION
)

# Premium users storage
PREMIUM_USERS_FILE = "premium_users.json"

def load_premium_users() -> Dict[str, Dict]:
    try:
        with open(PREMIUM_USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_premium_users(users: Dict[str, Dict]):
    with open(PREMIUM_USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

premium_users = load_premium_users()

def is_premium_user(user_id: int) -> bool:
    return str(user_id) in premium_users

def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    welcome_text = """
🤖 **Welcome to Premium File Storage Bot**

**Features:**
• Upload files up to 4GB
• High-speed Wasabi storage
• Direct download links
• Secure file sharing

**Premium Benefits:**
✅ Unlimited uploads
✅ Fast download speeds
✅ 4GB file support
✅ Priority support

Use /premium to get premium access!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Get Premium", callback_data="get_premium")],
        [InlineKeyboardButton("📤 Upload File", callback_data="upload_help"),
         InlineKeyboardButton("📥 My Files", callback_data="my_files")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("premium"))
async def premium_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if is_premium_user(user_id):
        user_data = premium_users[str(user_id)]
        expiry_date = user_data.get('expiry_date', 'Lifetime')
        await message.reply_text(
            f"✅ **You are a Premium User!**\n"
            f"📅 Expiry: {expiry_date}\n"
            f"Enjoy all premium features!"
        )
        return
    
    premium_text = f"""
💎 **Get Premium Access**

**Price:** ₹{Config.PREMIUM_PRICE}
**Payment Method:** GPay/UPI

**UPI ID:** `{Config.GPAY_UPI_ID}`

**Instructions:**
1. Send ₹{Config.PREMIUM_PRICE} to the UPI ID above
2. Take a screenshot of payment
3. Send the screenshot to admin for approval
4. You'll be activated within minutes!

**Benefits:**
• 4GB file upload support
• High-speed downloads
• Direct streaming links
• Unlimited storage
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Send Payment Proof", callback_data="send_payment")],
        [InlineKeyboardButton("👨‍💻 Contact Admin", url="https://t.me/your_admin_username")]
    ])
    
    await message.reply_text(premium_text, reply_markup=keyboard)

@app.on_message(filters.command("upload"))
async def upload_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not is_premium_user(user_id):
        await message.reply_text(
            "❌ **Premium Required**\n\n"
            "You need premium access to upload files.\n"
            "Use /premium to get premium features."
        )
        return
    
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text(
            "📤 **How to Upload:**\n\n"
            "Reply to a file with /upload command\n"
            "Example: Reply to a file and type `/upload`"
        )
        return
    
    await handle_file_upload(client, message.reply_to_message)

async def handle_file_upload(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not message.document and not message.video and not message.audio:
        await message.reply_text("❌ Please reply to a valid file (document, video, audio)")
        return
    
    file = message.document or message.video or message.audio
    file_size = file.file_size
    
    if file_size > Config.MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ File too large! Maximum size is 4GB.\n"
            f"Your file: {file_size / (1024**3):.2f}GB"
        )
        return
    
    # Generate unique file name
    file_extension = os.path.splitext(file.file_name)[1] if hasattr(file, 'file_name') else ".bin"
    unique_filename = f"{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.file_id}{file_extension}"
    
    status_msg = await message.reply_text("📤 Starting upload...")
    
    try:
        # Download file with progress
        download_path = await download_file_with_progress(client, message, status_msg)
        
        if not download_path:
            await status_msg.edit_text("❌ Download failed!")
            return
        
        # Upload to Wasabi with progress
        await upload_to_wasabi_with_progress(download_path, unique_filename, status_msg)
        
        # Generate download URL
        download_url = generate_download_url(unique_filename)
        
        # Clean up local file
        os.remove(download_path)
        
        # Send success message with download link
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Download Link", url=download_url)],
            [InlineKeyboardButton("📤 Share", switch_inline_query=unique_filename)]
        ])
        
        await status_msg.edit_text(
            f"✅ **File Uploaded Successfully!**\n\n"
            f"📁 File: `{unique_filename.split('/')[-1]}`\n"
            f"💾 Size: {file_size / (1024**3):.2f}GB\n"
            f"🔗 Direct Download Link Available",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload failed: {str(e)}")

async def download_file_with_progress(client: Client, message: Message, status_msg: Message) -> str:
    file = message.document or message.video or message.audio
    file_name = file.file_name or f"file_{file.file_id}"
    download_path = f"downloads/{file_name}"
    
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    def progress(current, total):
        percent = (current / total) * 100
        asyncio.create_task(
            status_msg.edit_text(
                f"📥 Downloading...\n"
                f"Progress: {current // (1024*1024)}MB / {total // (1024*1024)}MB\n"
                f"({percent:.1f}%)"
            )
        )
    
    await client.download_media(message, file_name=download_path, progress=progress)
    return download_path

async def upload_to_wasabi_with_progress(file_path: str, s3_key: str, status_msg: Message):
    file_size = os.path.getsize(file_path)
    
    def upload_progress(bytes_transferred):
        percent = (bytes_transferred / file_size) * 100
        asyncio.create_task(
            status_msg.edit_text(
                f"☁️ Uploading to Wasabi...\n"
                f"Progress: {bytes_transferred // (1024*1024)}MB / {file_size // (1024*1024)}MB\n"
                f"({percent:.1f}%)"
            )
        )
    
    # For large files, use multipart upload
    if file_size > 100 * 1024 * 1024:  # 100MB
        await multipart_upload(file_path, s3_key, upload_progress)
    else:
        s3_client.upload_file(
            file_path, 
            Config.WASABI_BUCKET, 
            s3_key,
            Callback=upload_progress
        )

async def multipart_upload(file_path: str, s3_key: str, progress_callback):
    # Implement multipart upload for large files
    transfer_config = boto3.s3.transfer.TransferConfig(
        multipart_threshold=100 * 1024 * 1024,  # 100MB
        max_concurrency=10,
        multipart_chunksize=50 * 1024 * 1024  # 50MB
    )
    
    s3_client.upload_file(
        file_path,
        Config.WASABI_BUCKET,
        s3_key,
        Config=transfer_config,
        Callback=progress_callback
    )

def generate_download_url(s3_key: str) -> str:
    """Generate presigned URL for download (valid for 1 week)"""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': Config.WASABI_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=604800  # 1 week
        )
        return url
    except ClientError as e:
        return f"Error generating URL: {str(e)}"

@app.on_message(filters.command("myfiles"))
async def my_files_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not is_premium_user(user_id):
        await message.reply_text("❌ Premium access required!")
        return
    
    try:
        # List user's files from Wasabi
        response = s3_client.list_objects_v2(
            Bucket=Config.WASABI_BUCKET,
            Prefix=f"{user_id}/"
        )
        
        if 'Contents' not in response:
            await message.reply_text("📭 No files found!")
            return
        
        files_text = "📁 **Your Files:**\n\n"
        for obj in response['Contents'][:10]:  # Show last 10 files
            file_name = obj['Key'].split('/')[-1]
            file_size = obj['Size'] / (1024*1024)  # MB
            files_text += f"• `{file_name}` ({file_size:.1f}MB)\n"
        
        await message.reply_text(files_text)
        
    except Exception as e:
        await message.reply_text(f"❌ Error fetching files: {str(e)}")

# Admin commands
@app.on_message(filters.command("addpremium") & filters.user(Config.ADMIN_IDS))
async def add_premium_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /addpremium <user_id> [days]")
        return
    
    try:
        target_user_id = int(message.command[1])
        days = int(message.command[2]) if len(message.command) > 2 else 30
        
        expiry_date = datetime.now().timestamp() + (days * 24 * 60 * 60)
        
        premium_users[str(target_user_id)] = {
            'added_by': message.from_user.id,
            'added_date': datetime.now().isoformat(),
            'expiry_date': expiry_date,
            'days': days
        }
        
        save_premium_users(premium_users)
        
        await message.reply_text(
            f"✅ Premium added for user {target_user_id}\n"
            f"Duration: {days} days"
        )
        
        # Notify user
        try:
            await client.send_message(
                target_user_id,
                f"🎉 **Premium Activated!**\n\n"
                f"Your premium access has been activated for {days} days!\n"
                f"You can now upload files up to 4GB."
            )
        except:
            pass
            
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@app.on_message(filters.command("userstats") & filters.user(Config.ADMIN_IDS))
async def user_stats_command(client: Client, message: Message):
    stats_text = f"📊 **Bot Statistics**\n\n"
    stats_text += f"👥 Total Premium Users: {len(premium_users)}\n"
    
    # Count active premium users
    active_users = 0
    for user_id, user_data in premium_users.items():
        expiry = user_data.get('expiry_date', 0)
        if expiry > datetime.now().timestamp():
            active_users += 1
    
    stats_text += f"✅ Active Premium Users: {active_users}\n"
    
    await message.reply_text(stats_text)

# Callback query handlers
@app.on_callback_query()
async def handle_callbacks(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "get_premium":
        await premium_command(client, callback_query.message)
    
    elif data == "upload_help":
        await callback_query.message.edit_text(
            "📤 **How to Upload Files:**\n\n"
            "1. Make sure you have premium access\n"
            "2. Send any file to the bot\n"
            "3. Reply to that file with /upload command\n"
            "4. Wait for upload to complete\n"
            "5. Get your direct download link!"
        )
    
    elif data == "my_files":
        await my_files_command(client, callback_query.message)
    
    elif data == "send_payment":
        await callback_query.message.edit_text(
            "📸 **Send Payment Proof**\n\n"
            "Please send the payment screenshot directly to this chat.\n"
            "Our admin will verify and activate your premium within minutes."
        )
    
    await callback_query.answer()

# Handle payment proof photos
@app.on_message(filters.photo & ~filters.user(Config.ADMIN_IDS))
async def handle_payment_proof(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is already premium
    if is_premium_user(user_id):
        await message.reply_text("✅ You already have premium access!")
        return
    
    # Forward to admin for approval
    for admin_id in Config.ADMIN_IDS:
        try:
            await client.send_message(
                admin_id,
                f"🤑 **New Payment Proof**\n\n"
                f"👤 User: {message.from_user.mention}\n"
                f"🆔 ID: `{user_id}`\n\n"
                f"Please verify and use /addpremium {user_id} to activate premium."
            )
            await client.forward_messages(admin_id, message.chat.id, message.id)
        except:
            pass
    
    await message.reply_text(
        "✅ Payment proof received!\n"
        "Admin has been notified. Your premium will be activated shortly."
    )

if __name__ == "__main__":
    print("🤖 Bot is starting...")
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    app.run()
