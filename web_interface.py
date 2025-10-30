from aiohttp import web
import json
from config import config

async def handle_root(request):
    """Web interface homepage"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>File Store Bot Admin</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 0; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                max-width: 1000px; 
                margin: 0 auto; 
                background: white; 
                padding: 40px; 
                border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                margin-top: 40px;
                margin-bottom: 40px;
            }
            h1 { 
                color: #333; 
                border-bottom: 3px solid #667eea; 
                padding-bottom: 15px;
                text-align: center;
                margin-bottom: 30px;
            }
            .stats { 
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                padding: 25px; 
                border-radius: 10px; 
                margin: 25px 0; 
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .admin-list { 
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 25px; 
                border-radius: 10px; 
                margin: 25px 0;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .commands { 
                background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                color: white;
                padding: 25px; 
                border-radius: 10px; 
                margin: 25px 0;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .btn { 
                background: rgba(255,255,255,0.2); 
                color: white; 
                padding: 12px 25px; 
                text-decoration: none; 
                border-radius: 8px; 
                display: inline-block; 
                margin: 8px;
                border: 2px solid white;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .btn:hover {
                background: white;
                color: #333;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .stat-item {
                margin: 10px 0;
                font-size: 18px;
            }
            .code {
                background: rgba(0,0,0,0.2);
                padding: 8px 12px;
                border-radius: 5px;
                font-family: monospace;
                margin: 5px 0;
                display: inline-block;
            }
            .section-title {
                font-size: 24px;
                margin-bottom: 20px;
                text-align: center;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 File Store Bot - Admin Panel</h1>
            
            <div class="stats">
                <div class="section-title">📊 Bot Statistics</div>
                <div class="stat-item"><strong>Total Admins:</strong> {admin_count}</div>
                <div class="stat-item"><strong>Max File Size:</strong> {max_size} MB</div>
                <div class="stat-item"><strong>Storage Chat ID:</strong> {storage_chat}</div>
                <div class="stat-item"><strong>Bot Username:</strong> @{bot_username}</div>
            </div>
            
            <div class="commands">
                <div class="section-title">🔧 Admin Commands</div>
                <p>Use these commands in Telegram bot:</p>
                <div class="code">/addadmin &lt;user_id&gt;</div> - Add new admin<br>
                <div class="code">/removeadmin &lt;user_id&gt;</div> - Remove admin<br>
                <div class="code">/admins</div> - List all admins<br>
                <div class="code">/get &lt;id&gt;</div> - Download file by ID<br>
                <div class="code">/link &lt;id&gt;</div> - Generate shareable link<br>
                <div class="code">/info &lt;id&gt;</div> - Get file information<br>
                <div class="code">/stats</div> - Bot statistics
            </div>
            
            <div class="admin-list">
                <div class="section-title">👑 Admin Management</div>
                <p>Access admin list and manage permissions:</p>
                <a href="/api/admins" class="btn">📋 View Admin List (JSON)</a>
                <a href="/api/stats" class="btn">📈 Bot Statistics API</a>
                <a href="https://t.me/{bot_username}" class="btn" target="_blank">🤖 Open Telegram Bot</a>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666;">
                <p>File Store Bot v2.0 • Web Interface • Port {web_port}</p>
            </div>
        </div>
    </body>
    </html>
    """.format(
        admin_count=len(config.ADMIN_IDS),
        max_size=config.MAX_FILE_SIZE,
        storage_chat=config.STORAGE_CHAT_ID,
        bot_username=config.BOT_USERNAME or "your_bot",
        web_port=config.WEB_PORT
    )
    return web.Response(text=html, content_type='text/html')

async def handle_api_admins(request):
    """API endpoint to get admin list"""
    admins_data = {
        "status": "success",
        "data": {
            "total_admins": len(config.ADMIN_IDS),
            "admin_ids": list(config.ADMIN_IDS),
            "max_file_size_mb": config.MAX_FILE_SIZE,
            "storage_chat_id": config.STORAGE_CHAT_ID,
            "bot_username": config.BOT_USERNAME
        }
    }
    return web.Response(
        text=json.dumps(admins_data, indent=2),
        content_type='application/json'
    )

async def handle_api_stats(request):
    """API endpoint for bot statistics"""
    stats_data = {
        "status": "success",
        "data": {
            "bot_status": "online",
            "total_admins": len(config.ADMIN_IDS),
            "max_file_size_mb": config.MAX_FILE_SIZE,
            "storage_chat_id": config.STORAGE_CHAT_ID,
            "web_interface": f"http://localhost:{config.WEB_PORT}",
            "allowed_file_types": config.ALLOWED_FILE_TYPES
        }
    }
    return web.Response(
        text=json.dumps(stats_data, indent=2),
        content_type='application/json'
    )

async def handle_api_health(request):
    """Health check endpoint"""
    health_data = {
        "status": "healthy",
        "service": "file_store_bot",
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }
    return web.Response(
        text=json.dumps(health_data, indent=2),
        content_type='application/json'
    )

def setup_web_server():
    """Setup and return web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', handle_root)
    app.router.add_get('/api/admins', handle_api_admins)
    app.router.add_get('/api/stats', handle_api_stats)
    app.router.add_get('/api/health', handle_api_health)
    
    return app

async def start_web_server():
    """Start the web server"""
    web_app = setup_web_server()
    runner = web.AppRunner(web_app)
    await runner.setup()
    
    site = web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT)
    await site.start()
    
    print(f"🌐 Web interface running on http://{config.WEB_HOST}:{config.WEB_PORT}")
    return runner
