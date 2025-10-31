from flask import Flask, render_template, jsonify
import threading
import time
import requests
from bot import get_bot_stats, upload_stats

app = Flask(__name__)

# Bot status variables
bot_status = {
    'status': 'unknown',
    'last_check': 'Never',
    'uptime': '0',
    'total_uploads': 0,
    'successful_uploads': 0,
    'failed_uploads': 0,
    'success_rate': 0
}

def update_bot_status():
    """Update bot status from the bot's statistics"""
    try:
        stats = get_bot_stats()
        bot_status.update(stats)
        bot_status['last_check'] = time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        bot_status['status'] = 'offline'
        bot_status['last_check'] = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"Error updating bot status: {e}")

def status_checker():
    """Background thread to check bot status"""
    while True:
        update_bot_status()
        time.sleep(10)  # Check every 10 seconds

@app.route('/')
def index():
    return render_template('index.html', status=bot_status)

@app.route('/api/status')
def api_status():
    update_bot_status()
    return jsonify(bot_status)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')})

if __name__ == '__main__':
    # Initial status update
    update_bot_status()
    
    # Start background status checking
    status_thread = threading.Thread(target=status_checker, daemon=True)
    status_thread.start()
    
    print("Starting status server on http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=False)
