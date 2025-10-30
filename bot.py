import os
import json
import asyncio
import aiofiles
from datetime import datetime, timedelta
from typing import Dict, List
import logging

import boto3
from botocore.exceptions import ClientError
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardButton, 
    InlineKeyboardMarkup, CallbackQuery
)
from pyrogram.enums import ParseMode

from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    user_data = premium_users.get(str(user_id))
    if user_data:
        expiry = user_data.get('expiry_date')
        if expiry and float(expiry) > datetime.now().timestamp():
            return True
    return False

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
        expiry_timestamp = float(user_data.get('expiry_date', 0))
        expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d %H:%M:%S')
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
    
    if not message.reply_to_message or not (message.reply_to_message.document or message.reply_to_message.video or message.reply_to_message.audio):
        await message.reply_text(
            "📤 **How to Upload:**\n\n"
            "Reply to a file with /upload command\n"
            "Example: Reply to a file and type `/upload`\n\n"
            "Supported files: Documents, Videos, Audio"
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
    file_name = getattr(file, 'file_name', None) or f"file_{file.file_id}"
    file_extension = os.path.splitext(file_name)[1]
    unique_filename = f"{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name}"
    
    status_msg = await message.reply_text("📤 Starting upload...")
    
    try:
        # Download file
        download_path = await download_file(client, message, status_msg)
        
        if not download_path:
            await status_msg.edit_text("❌ Download failed!")
            return
        
        # Upload to Wasabi
        success = await upload_to_wasabi(download_path, unique_filename, status_msg)
        
        if not success:
            await status_msg.edit_text("❌ Upload failed!")
            return
        
        # Generate download URL
        download_url = generate_download_url(unique_filename)
        
        # Clean up local file
        try:
            os.remove(download_path)
        except:
            pass
        
        # Send success message with download link
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Download Link", url=download_url)],
            [InlineKeyboardButton("📤 Share File", switch_inline_query=file_name)]
        ])
        
        file_size_mb = file_size / (1024 * 1024)
        file_size_gb = file_size / (1024 * 1024 * 1024)
        
        size_text = f"{file_size_mb:.1f}MB" if file_size_mb < 1024 else f"{file_size_gb:.2f}GB"
        
        await status_msg.edit_text(
            f"✅ **File Uploaded Successfully!**\n\n"
            f"📁 File: `{file_name}`\n"
            f"💾 Size: {size_text}\n"
            f"🔗 Direct Download Link Available\n"
            f"⏰ Link expires in 7 days",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        await status_msg.edit_text(f"❌ Upload failed: {str(e)}")

async def download_file(client: Client, message: Message, status_msg: Message) -> str:
    try:
        file = message.document or message.video or message.audio
        file_name = getattr(file, 'file_name', None) or f"file_{file.file_id}"
        download_path = f"downloads/{file_name}"
        
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)
        
        # Download with progress
        last_update_time = datetime.now()
        
        async def progress(current, total):
            nonlocal last_update_time
            # Update every 2 seconds to avoid spam
            if (datetime.now() - last_update_time).total_seconds() >= 2:
                percent = (current / total) * 100
                speed = current / (1024 * 1024)  # MB
                total_mb = total / (1024 * 1024)
                
                await status_msg.edit_text(
                    f"📥 Downloading...\n"
                    f"Progress: {current // (1024*1024)}MB / {total // (1024*1024)}MB\n"
                    f"({percent:.1f}%)\n"
                    f"Speed: {speed:.1f} MB/s"
                )
                last_update_time = datetime.now()
        
        await client.download_media(
            message,
            file_name=download_path,
            progress=progress
        )
        
        return download_path
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return None

async def upload_to_wasabi(file_path: str, s3_key: str, status_msg: Message) -> bool:
    try:
        file_size = os.path.getsize(file_path)
        
        # For files larger than 100MB, use multipart upload
        if file_size > 100 * 1024 * 1024:
            return await multipart_upload(file_path, s3_key, status_msg)
        else:
            # Simple upload for smaller files
            s3_client.upload_file(
                file_path, 
                Config.WASABI_BUCKET, 
                s3_key
            )
            await status_msg.edit_text("✅ Upload completed!")
            return True
            
    except Exception as e:
        logger.error(f"Wasabi upload error: {str(e)}")
        return False

async def multipart_upload(file_path: str, s3_key: str, status_msg: Message) -> bool:
    try:
        file_size = os.path.getsize(file_path)
        
        # Create multipart upload
        mpu = s3_client.create_multipart_upload(
            Bucket=Config.WASABI_BUCKET,
            Key=s3_key
        )
        mpu_id = mpu['UploadId']
        
        parts = []
        part_size = 50 * 1024 * 1024  # 50MB parts
        part_number = 1
        
        with open(file_path, 'rb') as file:
            while True:
                data = file.read(part_size)
                if not data:
                    break
                
                part = s3_client.upload_part(
                    Bucket=Config.WASABI_BUCKET,
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=mpu_id,
                    Body=data
                )
                
                parts.append({
                    'PartNumber': part_number,
                    'ETag': part['ETag']
                })
                
                # Update progress
                progress_percent = (part_number * part_size / file_size) * 100
                if progress_percent > 100:
                    progress_percent = 100
                
                await status_msg.edit_text(
                    f"☁️ Uploading to Wasabi...\n"
                    f"Progress: {progress_percent:.1f}%\n"
                    f"Part {part_number} completed"
                )
                
                part_number += 1
        
        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=Config.WASABI_BUCKET,
            Key=s3_key,
            UploadId=mpu_id,
            MultipartUpload={'Parts': parts}
        )
        
        await status_msg.edit_text("✅ Upload completed!")
        return True
        
    except Exception as e:
        logger.error(f"Multipart upload error: {str(e)}")
        # Abort upload on error
        try:
            s3_client.abort_multipart_upload(
                Bucket=Config.WASABI_BUCKET,
                Key=s3_key,
                UploadId=mpu_id
            )
        except:
            pass
        return False

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
        logger.error(f"URL generation error: {str(e)}")
        return "Error generating download URL"

@app.on_message(filters.command("download"))
async def download_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not is_premium_user(user_id):
        await message.reply_text("❌ Premium access required!")
        return
    
    if len(message.command) < 2:
        await message.reply_text("Usage: /download <filename>")
        return
    
    filename = message.command[1]
    s3_key = f"{user_id}/{filename}"
    
    try:
        # Check if file exists
        s3_client.head_object(Bucket=Config.WASABI_BUCKET, Key=s3_key)
        
        # Generate download URL
        download_url = generate_download_url(s3_key)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Download Now", url=download_url)]
        ])
        
        await message.reply_text(
            f"📥 **Download Ready**\n\n"
            f"File: `{filename}`\n"
            f"Link expires in 7 days\n\n"
            f"Click the button below to download:",
            reply_markup=keyboard
        )
        
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            await message.reply_text("❌ File not found!")
        else:
            await message.reply_text(f"❌ Error: {str(e)}")

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
        for obj in response['Contents'][:15]:  # Show last 15 files
            file_name = obj['Key'].split('/')[-1]
            file_size = obj['Size'] / (1024*1024)  # MB
            last_modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M')
            
            files_text += f"• `{file_name}`\n"
            files_text += f"  Size: {file_size:.1f}MB | Modified: {last_modified}\n\n"
        
        files_text += f"\nTotal files: {len(response['Contents'])}"
        
        await message.reply_text(files_text)
        
    except Exception as e:
        logger.error(f"List files error: {str(e)}")
        await message.reply_text(f"❌ Error fetching files: {str(e)}")

@app.on_message(filters.command("delete"))
async def delete_file_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not is_premium_user(user_id):
        await message.reply_text("❌ Premium access required!")
        return
    
    if len(message.command) < 2:
        await message.reply_text("Usage: /delete <filename>")
        return
    
    filename = message.command[1]
    s3_key = f"{user_id}/{filename}"
    
    try:
        # Delete file from Wasabi
        s3_client.delete_object(
            Bucket=Config.WASABI_BUCKET,
            Key=s3_key
        )
        
        await message.reply_text(f"✅ File `{filename}` deleted successfully!")
        
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        await message.reply_text(f"❌ Error deleting file: {str(e)}")

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
                f"You can now upload files up to 4GB.\n\n"
                f"Use /upload to start uploading files!"
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
        if float(expiry) > datetime.now().timestamp():
            active_users += 1
    
    stats_text += f"✅ Active Premium Users: {active_users}\n"
    
    # Get storage stats
    try:
        total_size = 0
        total_files = 0
        
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=Config.WASABI_BUCKET):
            if 'Contents' in page:
                total_files += len(page['Contents'])
                for obj in page['Contents']:
                    total_size += obj['Size']
        
        stats_text += f"📁 Total Files: {total_files}\n"
        stats_text += f"💾 Total Storage Used: {total_size / (1024**3):.2f} GB\n"
    
    except Exception as e:
        stats_text += f"📁 Storage stats: Unable to calculate\n"
    
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
            "3. Reply to that file with `/upload` command\n"
            "4. Wait for upload to complete\n"
            "5. Get your direct download link!\n\n"
            "**Supported files:** Documents, Videos, Audio\n"
            "**Max size:** 4GB"
        )
    
    elif data == "my_files":
        await my_files_command(client, callback_query.message)
    
    elif data == "send_payment":
        await callback_query.message.edit_text(
            "📸 **Send Payment Proof**\n\n"
            "Please send the payment screenshot directly to this chat.\n"
            "Our admin will verify and activate your premium within minutes.\n\n"
            f"**Amount:** ₹{Config.PREMIUM_PRICE}\n"
            f"**UPI ID:** `{Config.GPAY_UPI_ID}`"
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
                f"🆔 ID: `{user_id}`\n"
                f"📛 Username: @{message.from_user.username}\n\n"
                f"Use this command to activate premium:\n"
                f"`/addpremium {user_id} 30`"
            )
            await client.forward_messages(admin_id, message.chat.id, message.id)
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
    
    await message.reply_text(
        "✅ Payment proof received!\n"
        "Admin has been notified. Your premium will be activated shortly.\n\n"
        "You will receive a confirmation message when activated."
    )

if __name__ == "__main__":
    print("🤖 Bot is starting...")
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    app.run()
