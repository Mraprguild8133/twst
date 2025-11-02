import os
import logging
import feedparser
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# Import configuration
from config import config

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_last_link():
    """Loads the last sent link from the persistence file."""
    if os.path.exists(config.LAST_SENT_FILE):
        with open(config.LAST_SENT_FILE, 'r') as f:
            return f.read().strip()
    return ""

def save_last_link(link):
    """Saves the latest link to the persistence file."""
    with open(config.LAST_SENT_FILE, 'w') as f:
        f.write(link)

async def check_new_posts(context: ContextTypes.DEFAULT_TYPE):
    """The function scheduled to run periodically to check the RSS feed."""
    logger.info("Starting scheduled RSS feed check...")

    try:
        last_sent_link = load_last_link()
        feed = feedparser.parse(config.RSS_FEED_URL)
        
        # Check if feed was parsed successfully
        if feed.bozo:
            logger.error(f"RSS feed parsing error: {feed.bozo_exception}")
            return
            
    except Exception as e:
        logger.error(f"Error fetching RSS feed: {e}")
        return

    new_posts = []

    # Iterate through entries in reverse chronological order (newest first)
    for entry in feed.entries:
        link = entry.link
        if link == last_sent_link:
            # Stop when we hit the last known sent link
            break
        
        # Prepare post data
        title = entry.title
        # Use link in message
        message = f"<b>{title}</b>\n<a href='{link}'>Read Full Story</a>"
        new_posts.append((link, message))

    if not new_posts:
        logger.info("No new posts found.")
        return

    # Posts were collected newest to oldest. Reverse to send oldest new post first.
    new_posts.reverse()

    # Send all new posts to the chat
    for link, message in new_posts:
        try:
            await context.bot.send_message(
                chat_id=config.CHAT_ID,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            logger.info(f"Sent new post: {link}")
        except Exception as e:
            logger.error(f"Error sending message for link {link}: {e}")
    
    # After all new posts are sent, update the last sent link to the newest one.
    if new_posts:
        latest_link_in_feed = feed.entries[0].link
        save_last_link(latest_link_in_feed)
        logger.info(f"Updated last sent link to: {latest_link_in_feed}")

async def start_command(update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    job_name = 'rss_checker'
    if context.job_queue.get_jobs_by_name(job_name):
        text = "Bot is already running its scheduled feed check."
    else:
        context.job_queue.run_repeating(
            check_new_posts, 
            interval=config.CHECK_INTERVAL_SECONDS, 
            first=1,
            name=job_name
        )
        text = (f"RSS Feed Bot Started! I will check the feed every {config.CHECK_INTERVAL_SECONDS} seconds.\n"
                f"Feed URL: {config.RSS_FEED_URL}\n"
                f"Sending updates to Chat ID: {config.CHAT_ID}")

    await update.message.reply_text(text)

async def status_command(update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status and last checked time"""
    job_name = 'rss_checker'
    jobs = context.job_queue.get_jobs_by_name(job_name)
    
    if jobs:
        status_text = "Bot is actively monitoring the feed."
    else:
        status_text = "Bot is not currently monitoring the feed. Use /start to begin."
    
    last_link = load_last_link()
    if last_link:
        status_text += f"\nLast sent item: {last_link[:50]}..."
    else:
        status_text += "\nNo items sent yet."
    
    await update.message.reply_text(status_text)

async def stop_command(update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the RSS monitoring"""
    job_name = 'rss_checker'
    jobs = context.job_queue.get_jobs_by_name(job_name)
    
    for job in jobs:
        job.schedule_removal()
    
    await update.message.reply_text("RSS monitoring stopped.")

async def force_check_command(update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger an RSS feed check"""
    await update.message.reply_text("Manually checking for new posts...")
    await check_new_posts(context)

def main():
    """Starts the bot using the Application builder pattern."""
    try:
        # Validate configuration
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    logger.info("Initializing Telegram Application...")
    
    # Create the Application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("check", force_check_command))

    logger.info("Bot is ready. Start polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
