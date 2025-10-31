from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

class MessageTemplates:
    """Modern, responsive message templates"""
    
    @staticmethod
    def welcome_message() -> str:
        return """
🎨 *Welcome to Advanced Image Uploader Pro* 🚀

✨ *Features:*
• 🖼️ High-speed image uploads
• 📊 Real-time upload statistics  
• 🎯 Smart image optimization
• 🔒 Secure cloud storage
• 📱 Multi-format support

📦 *Supported Formats:* JPEG, PNG, GIF, WEBP
💾 *Max Size:* 32MB per file

Send me an image to get started!
        """
    
    @staticmethod
    def upload_success_template(image_url: str, stats: dict) -> str:
        return f"""
✅ *Upload Successful!*

🔗 *Direct URL:* `{image_url}`
📊 *Stats:* {stats['size_mb']:.2f}MB • {stats['optimization_saved']:.1f}% optimized
⏱️ *Processing Time:* {stats['processing_time']:.2f}s

💡 *Pro Tip:* Use /batch for multiple uploads!
        """
    
    @staticmethod
    def create_upload_keyboard(image_url: str, delete_url: str) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🌐 Open URL", url=image_url),
                InlineKeyboardButton("🗑️ Delete", url=delete_url)
            ],
            [
                InlineKeyboardButton("📋 Copy URL", callback_data=f"copy_{image_url}"),
                InlineKeyboardButton("🔄 Upload More", callback_data="upload_more")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def error_template(error_type: str, details: str = "") -> str:
        templates = {
            "rate_limit": """
🚫 *Rate Limit Exceeded*

Please wait {time} seconds before uploading more images.

💡 *Premium users get higher limits!*
            """,
            "file_too_large": """
📁 *File Too Large*

Your file ({actual_size}MB) exceeds the {max_size}MB limit.

💡 *Try compressing your image first!*
            """,
            "upload_failed": """
❌ *Upload Failed*

Error: {details}

🔧 *Our team has been notified and will fix this shortly.*
            """
        }
        return templates.get(error_type, "An error occurred.")

templates = MessageTemplates()
