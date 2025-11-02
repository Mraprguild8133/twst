from aiohttp import web
import json
from datetime import datetime
from rss_bot import rss_bot, config

async def status_handler(request):
    """Handle status requests"""
    bot_status = rss_bot.get_bot_status()
    
    # Calculate human-readable uptime
    uptime_seconds = bot_status['uptime_seconds']
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RSS Bot Status</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }}
            .container {{
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .status-card {{
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin: 15px 0;
                border-left: 5px solid #007bff;
            }}
            .status-online {{
                border-left-color: #28a745;
            }}
            .status-warning {{
                border-left-color: #ffc107;
            }}
            .status-error {{
                border-left-color: #dc3545;
            }}
            .metric {{
                display: flex;
                justify-content: space-between;
                margin: 10px 0;
                padding: 8px;
                background: white;
                border-radius: 5px;
            }}
            .metric-label {{
                font-weight: bold;
                color: #555;
            }}
            .metric-value {{
                color: #007bff;
                font-weight: bold;
            }}
            .last-check {{
                font-size: 0.9em;
                color: #666;
                text-align: right;
            }}
            h1 {{
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .subtitle {{
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 RSS Telegram Bot</h1>
                <p class="subtitle">Real-time Monitoring Status</p>
            </div>
            
            <div class="status-card status-online">
                <h2>🟢 Bot Status: Online</h2>
                <div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value">{hours}h {minutes}m {seconds}s</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Bot Started:</span>
                    <span class="metric-value">{bot_status['bot_start_time'][:19].replace('T', ' ')}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Check:</span>
                    <span class="metric-value">
                        {bot_status['last_check_time'][:19].replace('T', ' ') if bot_status['last_check_time'] else 'Never'}
                    </span>
                </div>
            </div>
            
            <div class="status-card">
                <h2>📊 Statistics</h2>
                <div class="metric">
                    <span class="metric-label">Total Posts Sent:</span>
                    <span class="metric-value">{bot_status['total_posts_sent']}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Check Interval:</span>
                    <span class="metric-value">{bot_status['check_interval'] // 60} minutes</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Daily Summary:</span>
                    <span class="metric-value">{bot_status['daily_summary_hour']}:00</span>
                </div>
            </div>
            
            <div class="status-card">
                <h2>📡 Feed Information</h2>
                <div class="metric">
                    <span class="metric-label">RSS Feed URL:</span>
                    <span class="metric-value" style="font-size: 0.8em;">{bot_status['feed_url']}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Web Server Port:</span>
                    <span class="metric-value">{bot_status['web_port']}</span>
                </div>
            </div>
            
            {f'<div class="status-card status-warning"><h3>⚠️ Last Error</h3><p>{bot_status["last_error"]}</p></div>' if bot_status['last_error'] else ''}
            
            <div class="last-check">
                Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    
    return web.Response(text=html_content, content_type='text/html')

async def api_status_handler(request):
    """JSON API endpoint for bot status"""
    bot_status = rss_bot.get_bot_status()
    return web.Response(
        text=json.dumps(bot_status, indent=2),
        content_type='application/json'
    )

async def health_handler(request):
    """Simple health check endpoint"""
    return web.Response(text='OK')

def create_web_app():
    """Create and configure web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', status_handler)
    app.router.add_get('/status', status_handler)
    app.router.add_get('/api/status', api_status_handler)
    app.router.add_get('/health', health_handler)
    
    return app

async def start_web_server():
    """Start the web server"""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, config.WEB_SERVER_HOST, config.WEB_SERVER_PORT)
    await site.start()
    
    print(f"🌐 Web server running on http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}")
    print(f"📊 Status page: http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}/status")
    print(f"🔗 API endpoint: http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}/api/status")
    
    return runner
