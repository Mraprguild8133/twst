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
        stats_text = (
            f"<b>📈 RSS Bot Statistics</b>\n\n"
            f"📊 Total posts sent: <b>{len(self.sent_links)}</b>\n"
            f"📅 Bot started: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"⏰ Check interval: <b>{config.CHECK_INTERVAL_SECONDS // 60} minutes</b>\n"
            f"📢 Daily summary: <b>{config.DAILY_SUMMARY_HOUR}:00</b>\n\n"
            f"<i>Bot is running smoothly! 🚀</i>"
        )
        await update.message.reply_text(stats_text, parse_mode='HTML')

# Global bot instance
rss_bot = RSSBot()

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
    application.add_handler(CommandHandler("start", rss_bot.start_command))
    application.add_handler(CommandHandler("status", rss_bot.status_command))
    application.add_handler(CommandHandler("stop", rss_bot.stop_command))
    application.add_handler(CommandHandler("check", rss_bot.force_check_command))
    application.add_handler(CommandHandler("stats", rss_bot.stats_command))

    logger.info("Bot is ready. Start polling...")
    logger.info(f"Will check feed every {config.CHECK_INTERVAL_SECONDS} seconds")
    logger.info(f"Daily summary at {config.DAILY_SUMMARY_HOUR}:00")
    
    application.run_polling()

if __name__ == "__main__":
    main()
