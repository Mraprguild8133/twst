# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# Chat IDs
SOURCE_CHAT_ID = int(os.getenv('SOURCE_CHAT_ID', -1001234567890))
DESTINATION_CHAT_ID = int(os.getenv('DESTINATION_CHAT_ID', -1009876543210))

# Bot Settings
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')
POLLING_TIMEOUT = int(os.getenv('POLLING_TIMEOUT', 10))
LONG_POLLING_TIMEOUT = int(os.getenv('LONG_POLLING_TIMEOUT', 5))

# Content types to forward
FORWARD_CONTENT_TYPES = [
    'text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker',
    'animation', 'poll', 'location', 'contact', 'dice', 'video_note'
]
