#!/usr/bin/env python3
# --------------------------------------------------------------------------------------
# Telegram RSS Bot for Gadgets 360 News
# --------------------------------------------------------------------------------------
# Dependencies:
# pip install python-telegram-bot feedparser beautifulsoup4 python-dotenv
# --------------------------------------------------------------------------------------

import logging
import feedparser
import re
import json
import os
from datetime import datetime
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes

# Import configuration - FIXED IMPORT
import config

# Use configuration values
BOT_TOKEN = config.BOT_TOKEN
RSS_URL = config.RSS_URL
SEEN_LINKS_FILE = config.SEEN_LINKS_FILE
ADMIN_IDS = config.ADMIN_IDS

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Persistent storage for seen links
def load_seen_links():
    """Load seen links from JSON file."""
    try:
        if os.path.exists(SEEN_LINKS_FILE):
            with open(SEEN_LINKS_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('seen_links', []))
    except Exception as e:
        logger.error(f"Error loading seen links: {e}")
    return set()

def save_seen_links(seen_links):
    """Save seen links to JSON file."""
    try:
        data = {
            'seen_links': list(seen_links),
            'last_updated': datetime.now().isoformat()
        }
        with open(SEEN_LINKS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving seen links: {e}")

# Global set for seen links
SEEN_LINKS = load_seen_links()

def extract_image_url(entry):
    """
    Attempts to find a featured image URL in the RSS entry fields.
    Prioritizes media:content, then looks for an enclosure, then in summary HTML.
    """
    # 1. Check for media_content (common for featured images)
    if 'media_content' in entry and entry.media_content:
        for media in entry.media_content:
            if hasattr(media, 'get') and media.get('url'):
                return media['url']
            elif hasattr(media, 'url'):
                return media.url
    
    # 2. Check for enclosures (often used for podcasts/media, but sometimes images)
    if 'enclosures' in entry and entry.enclosures:
        for enclosure in entry.enclosures:
            enclosure_type = enclosure.get('type', '') if hasattr(enclosure, 'get') else getattr(enclosure, 'type', '')
            if enclosure_type.startswith('image/'):
                if hasattr(enclosure, 'get') and enclosure.get('href'):
                    return enclosure['href']
                elif hasattr(enclosure, 'href'):
                    return enclosure.href

    # 3. Fallback: Search the summary/description HTML for an <img> tag
    summary_text = entry.get('summary', '') or entry.get('description', '')
    if summary_text:
        # Simple regex to find the first image src in the summary
        img_match = re.search(r'<img[^>]+src="([^">]+)"', summary_text)
        if img_match:
            return img_match.group(1)
            
    return None

def clean_html(text):
    """Remove HTML tags from text and clean it up."""
    if not text:
        return "No summary available."
    
    # Remove HTML tags
    clean = re.sub('<[^<]+?>', '', text)
    # Replace multiple spaces with single space
    clean = re.sub('\s+', ' ', clean)
    # Strip leading/trailing whitespace
    return clean.strip()

def format_news_message(entry):
    """Format the news entry into a nice Telegram message."""
    title = entry.title
    link = entry.link
    summary = clean_html(entry.get('summary') or entry.get('description', ''))
    
    # Truncate summary if too long
    if len(summary) > 400:
        summary = summary[:397] + "..."
    
    # Format published date if available
    published = ""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            from time import mktime
            dt = datetime.fromtimestamp(mktime(entry.published_parsed))
            published = f"📅 {dt.strftime('%Y-%m-%d %H:%M')}\n\n"
        except:
            pass
    
    message_text = (
        f"🚀 <b>LATEST GADGETS 360 NEWS</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{published}"
        f"{summary}\n\n"
        f"🔗 <a href='{link}'>Read Full Article on Gadgets 360</a>"
    )
    
    return message_text, summary

# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        config.WELCOME_MESSAGE.format(user_name=user.mention_html())
    )
    logger.info(f"User {user.id} started the bot")

# Command handler for /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information."""
    await update.message.reply_html(config.HELP_MESSAGE)
    logger.info(f"User {update.effective_user.id} requested help")

# Command handler for /latest
async def get_latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and sends the latest, unsent article from the RSS feed."""
    user = update.effective_user
    await update.message.reply_text("📡 Fetching the latest news from Gadgets 360...")
    logger.info(f"User {user.id} requested latest news")

    try:
        # Parse the RSS feed
        feed = feedparser.parse(RSS_URL)

        if not feed.entries:
            await update.message.reply_text("❌ Could not find any news entries in the feed. Please try again later.")
            logger.warning("No entries found in RSS feed")
            return

        # Get the very first (latest) entry
        entry = feed.entries[0]
        
        # Check if we have already processed this link
        if entry.link in SEEN_LINKS:
            await update.message.reply_text(
                "ℹ️ The latest article has already been sent. "
                "Gadgets 360 updates their feed periodically. "
                "Try again in a few minutes for newer content!"
            )
            logger.info(f"Duplicate article detected: {entry.link}")
            return

        # Extract and format details
        message_text, summary = format_news_message(entry)
        
        # Look for the image
        image_url = extract_image_url(entry)
        
        logger.info(f"Sending new article: {entry.title}")

        # Send the news item
        if image_url:
            try:
                # Use send_photo if an image is found
                await update.message.reply_photo(
                    photo=image_url,
                    caption=message_text,
                    parse_mode=constants.ParseMode.HTML,
                    disable_notification=True
                )
            except Exception as e:
                logger.warning(f"Failed to send photo, falling back to text: {e}")
                await update.message.reply_html(
                    text=message_text,
                    disable_web_page_preview=False,
                    disable_notification=True
                )
        else:
            # Fallback to simple message if no image is found
            await update.message.reply_html(
                text=message_text,
                disable_web_page_preview=False,
                disable_notification=True
            )
        
        # Mark the link as seen and save
        SEEN_LINKS.add(entry.link)
        save_seen_links(SEEN_LINKS)
        
        logger.info(f"Successfully sent and saved article: {entry.title}")

    except Exception as e:
        logger.error(f"Error fetching or sending news: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error processing the RSS feed. "
            "Please try again in a few moments."
        )

# Command handler for /stats (admin only)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics (admin only)."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ This command is for administrators only.")
        return
    
    stats_text = (
        f"🤖 <b>Bot Statistics</b>\n\n"
        f"• Total tracked articles: {len(SEEN_LINKS)}\n"
        f"• RSS Feed: {RSS_URL}\n"
        f"• Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"• Active users: 1 (basic implementation)"
    )
    
    await update.message.reply_html(stats_text)
    logger.info(f"Admin {user.id} requested stats")

def main() -> None:
    """Start the bot."""
    # Validate bot token
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        logger.error("Please set your BOT_TOKEN in config.py or .env file")
        print("❌ FATAL ERROR: Please set your BOT_TOKEN in config.py or .env file")
        return

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("latest", get_latest_news))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Start the bot
    logger.info("Bot is starting...")
    print("🤖 Bot is starting. Press Ctrl-C to stop.")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\n👋 Bot stopped.")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"❌ Bot crashed: {e}")

if __name__ == "__main__":
    main()
