import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
import feedparser
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# Import configuration
from config import config

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RSSBot:
    def __init__(self):
        self.sent_links = self.load_sent_links()
        self.bot_start_time = datetime.now()
        self.last_check_time = None
        self.last_error = None
        self.total_posts_sent = len(self.sent_links)
        
    def load_last_link(self):
        """Loads the last sent link from the persistence file."""
        if os.path.exists(config.LAST_SENT_FILE):
            with open(config.LAST_SENT_FILE, 'r') as f:
                return f.read().strip()
        return ""

    def save_last_link(self, link):
        """Saves the latest link to the persistence file."""
        with open(config.LAST_SENT_FILE, 'w') as f:
            f.write(link)

    def load_sent_links(self):
        """Load all sent links from JSON file to avoid duplicates across restarts."""
        if os.path.exists(config.SENT_LINKS_FILE):
            try:
                with open(config.SENT_LINKS_FILE, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading sent links: {e}")
        return set()

    def save_sent_links(self):
        """Save sent links to JSON file."""
        try:
            with open(config.SENT_LINKS_FILE, 'w') as f:
                json.dump(list(self.sent_links), f)
        except Exception as e:
            logger.error(f"Error saving sent links: {e}")

    async def check_new_posts(self, context: ContextTypes.DEFAULT_TYPE):
        """The function scheduled to run periodically to check the RSS feed."""
        logger.info("Starting scheduled RSS feed check...")
        self.last_check_time = datetime.now()

        try:
            feed = feedparser.parse(config.RSS_FEED_URL)
            self.last_error = None
            
            # Check if feed was parsed successfully
            if feed.bozo:
                error_msg = f"RSS feed parsing error: {feed.bozo_exception}"
                logger.error(error_msg)
                self.last_error = error_msg
                return
                
        except Exception as e:
            error_msg = f"Error fetching RSS feed: {e}"
            logger.error(error_msg)
            self.last_error = error_msg
            return

        new_posts = []

        # Iterate through entries in reverse chronological order (newest first)
        for entry in feed.entries:
            link = entry.link
            
            # Skip if we've already sent this link
            if link in self.sent_links:
                continue
            
            # Prepare post data
            title = entry.title
            published = getattr(entry, 'published', '')
            summary = getattr(entry, 'summary', '')[:200]  # Truncate summary
            
            # Create formatted message
            message = f"<b>📰 {title}</b>\n"
            if published:
                message += f"📅 {published}\n"
            if summary:
                message += f"📝 {summary}...\n"
            message += f"🔗 <a href='{link}'>Read Full Story</a>"
            
            new_posts.append((link, message))

        if not new_posts:
            logger.info("No new posts found.")
            return

        # Send all new posts to the chat
        sent_count = 0
        for link, message in new_posts:
            try:
                await context.bot.send_message(
                    chat_id=config.CHAT_ID,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                self.sent_links.add(link)
                sent_count += 1
                self.total_posts_sent += 1
                logger.info(f"Sent new post: {link}")
                
                # Add small delay between messages to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error sending message for link {link}: {e}")
        
        # Save the updated sent links
        self.save_sent_links()
        
        # Update last sent link to the newest one
        if sent_count > 0:
            latest_link = feed.entries[0].link
            self.save_last_link(latest_link)
            logger.info(f"Updated last sent link to: {latest_link}")
            logger.info(f"Successfully sent {sent_count} new posts")

    async def send_daily_summary(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a daily summary of RSS feed activity."""
        try:
            feed = feedparser.parse(config.RSS_FEED_URL)
            
            if feed.bozo:
                logger.error(f"RSS feed parsing error in daily summary: {feed.bozo_exception}")
                return

            # Get today's date for filtering
            today = datetime.now().date()
            today_posts = []
            
            for entry in feed.entries[:10]:
                link = entry.link
                published = getattr(entry, 'published_parsed', None)
                
                if published:
                    published_date = datetime(*published[:6]).date()
                    if published_date == today and link not in self.sent_links:
                        today_posts.append(entry)

            if today_posts:
                summary_message = f"<b>📊 Daily RSS Summary - {today.strftime('%Y-%m-%d')}</b>\n\n"
                summary_message += f"Found {len(today_posts)} new posts today:\n\n"
                
                for i, entry in enumerate(today_posts[:5], 1):
                    title = entry.title
                    link = entry.link
                    summary_message += f"{i}. <a href='{link}'>{title}</a>\n"
                
                if len(today_posts) > 5:
                    summary_message += f"\n... and {len(today_posts) - 5} more posts."
                
                summary_message += f"\n\n🔔 Use /check to fetch all new posts now!"
                
            else:
                summary_message = f"<b>📊 Daily RSS Summary - {today.strftime('%Y-%m-%d')}</b>\n\n"
                summary_message += "No new posts found today.\n"
                summary_message += "The bot is still actively monitoring the feed. ✅"

            await context.bot.send_message(
                chat_id=config.CHAT_ID,
                text=summary_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info("Daily summary sent successfully")

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a welcome message when the /start command is issued."""
        job_name = 'rss_checker'
        daily_job_name = 'daily_summary'
        
        jobs_running = bool(context.job_queue.get_jobs_by_name(job_name))
        daily_jobs_running = bool(context.job_queue.get_jobs_by_name(daily_job_name))

        if not jobs_running:
            context.job_queue.run_repeating(
                self.check_new_posts, 
                interval=config.CHECK_INTERVAL_SECONDS, 
                first=10,
                name=job_name
            )

        if not daily_jobs_running:
            now = datetime.now()
            target_time = now.replace(hour=config.DAILY_SUMMARY_HOUR, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += timedelta(days=1)
            
            seconds_until_target = (target_time - now).total_seconds()
            
            context.job_queue.run_repeating(
                self.send_daily_summary,
                interval=86400,
                first=seconds_until_target,
                name=daily_job_name
            )

        text = (
            f"🤖 <b>RSS Feed Bot Started!</b>\n\n"
            f"✅ <b>Real-time monitoring:</b> Every {config.CHECK_INTERVAL_SECONDS // 60} minutes\n"
            f"📊 <b>Daily summary:</b> {config.DAILY_SUMMARY_HOUR}:00 daily\n"
            f"📡 <b>Feed URL:</b> {config.RSS_FEED_URL}\n"
            f"👥 <b>Chat ID:</b> {config.CHAT_ID}\n\n"
            f"<i>Bot is now actively monitoring for new posts!</i>"
        )

        await update.message.reply_text(text, parse_mode='HTML')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check bot status and statistics."""
        job_name = 'rss_checker'
        daily_job_name = 'daily_summary'
        
        jobs = context.job_queue.get_jobs_by_name(job_name)
        daily_jobs = context.job_queue.get_jobs_by_name(daily_job_name)
        
        status_text = "<b>🤖 RSS Bot Status</b>\n\n"
        
        if jobs:
            next_check = jobs[0].next_t
            status_text += f"✅ <b>Real-time monitoring:</b> Active\n"
            status_text += f"   Next check: {next_check.strftime('%H:%M:%S')}\n"
        else:
            status_text += "❌ <b>Real-time monitoring:</b> Inactive\n"
        
        if daily_jobs:
            next_daily = daily_jobs[0].next_t
            status_text += f"✅ <b>Daily summary:</b> Active\n"
            status_text += f"   Next summary: {next_daily.strftime('%Y-%m-%d %H:%M')}\n"
        else:
            status_text += "❌ <b>Daily summary:</b> Inactive\n"
        
        status_text += f"\n<b>Statistics:</b>\n"
        status_text += f"📊 Total sent posts: {len(self.sent_links)}\n"
        status_text += f"📡 Monitoring feed: {config.RSS_FEED_URL}\n"
        
        last_link = self.load_last_link()
        if last_link:
            status_text += f"📎 Last sent: {last_link[:30]}...\n"
        else:
            status_text += "📎 Last sent: None\n"
        
        status_text += f"\nUse /check to manually fetch new posts now!"

        await update.message.reply_text(status_text, parse_mode='HTML')

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop the RSS monitoring."""
        job_name = 'rss_checker'
        daily_job_name = 'daily_summary'
        
        jobs = context.job_queue.get_jobs_by_name(job_name)
        daily_jobs = context.job_queue.get_jobs_by_name(daily_job_name)
        
        stopped_count = 0
        for job in jobs + daily_jobs:
            job.schedule_removal()
            stopped_count += 1
        
        if stopped_count > 0:
            await update.message.reply_text(f"🛑 Stopped {stopped_count} monitoring job(s).")
        else:
            await update.message.reply_text("No active monitoring jobs found.")

    async def force_check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger an RSS feed check."""
        await update.message.reply_text("🔄 Manually checking for new posts...")
        await self.check_new_posts(context)
        await update.message.reply_text("✅ Manual check completed!")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics."""
        uptime = datetime.now() - self.bot_start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        stats_text = (
            f"<b>📈 RSS Bot Statistics</b>\n\n"
            f"📊 Total posts sent: <b>{self.total_posts_sent}</b>\n"
            f"⏰ Uptime: <b>{hours}h {minutes}m {seconds}s</b>\n"
            f"📅 Bot started: <b>{self.bot_start_time.strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"🔄 Check interval: <b>{config.CHECK_INTERVAL_SECONDS // 60} minutes</b>\n"
            f"📢 Daily summary: <b>{config.DAILY_SUMMARY_HOUR}:00</b>\n"
            f"🌐 Web status: <b>Port {config.WEB_SERVER_PORT}</b>\n\n"
            f"<i>Bot is running smoothly! 🚀</i>"
        )
        await update.message.reply_text(stats_text, parse_mode='HTML')

    def get_bot_status(self):
        """Get bot status for web interface."""
        return {
            "status": "running",
            "bot_start_time": self.bot_start_time.isoformat(),
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "total_posts_sent": self.total_posts_sent,
            "last_error": self.last_error,
            "uptime_seconds": int((datetime.now() - self.bot_start_time).total_seconds()),
            "feed_url": config.RSS_FEED_URL,
            "check_interval": config.CHECK_INTERVAL_SECONDS,
            "daily_summary_hour": config.DAILY_SUMMARY_HOUR,
            "web_port": config.WEB_SERVER_PORT
        }

# Global bot instance
rss_bot = RSSBot()
