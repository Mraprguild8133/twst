# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RSS_URL = os.getenv("RSS_URL", "https://www.gadgets360.com/rss/news")

# Bot Settings
ADMIN_IDS = [123456789]  # Replace with your Telegram user ID
UPDATE_INTERVAL = 300  # 5 minutes for automatic updates

# File paths
SEEN_LINKS_FILE = "data/seen_links.json"
LOG_FILE = "logs/bot.log"

# Message templates
WELCOME_MESSAGE = """
Hello {user_name}! 👋

I am an RSS bot tracking the latest news from Gadgets 360.

<b>Commands:</b>
/start - Show this welcome message
/latest - Get the latest news article
/help - Show help information

Stay updated with the latest technology news!
"""

HELP_MESSAGE = """
📚 <b>Available Commands:</b>

/start - Show welcome message
/latest - Get the latest news article from Gadgets 360
/help - Show this help message

<b>About this bot:</b>
• Fetches real-time news from Gadgets 360 RSS feed
• Shows article summaries with images when available
• Provides direct links to full articles

<b>Source:</b> Gadgets 360 News RSS Feed
"""
