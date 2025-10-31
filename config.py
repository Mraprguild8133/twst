import os

class Config:
    BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    GPLINKS_API = os.environ.get('GPLINKS_API', '')
    SHRINKEARN_API = os.environ.get('SHRINKEARN_API', '')
    SHRTFLY_API = os.environ.get('SHRTFLY_API', '')
    FCLC_API = os.environ.get('FCLC_API', '')
    USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'
    WEBHOOK_PORT = int(os.environ.get('PORT', 5000))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
    WELCOME_IMAGE_URL = os.environ.get('WELCOME_IMAGE_URL', 'https://iili.io/Kcbrql9.th.jpg')
    
    SUPPORTED_SERVICES = {
        'gplinks': {
            'name': 'GPLinks',
            'api_url': 'https://gplinks.in/api',
            'requires_key': True
        },
        'shrinkearn': {
            'name': 'ShrinkEarn',
            'api_url': 'https://shrinkearn.com/api',
            'requires_key': True
        },
        'shrtfly': {
            'name': 'ShrtFly',
            'api_url': 'https://shrtfly.com/api',
            'requires_key': True
        },
        'fclc': {
            'name': 'FC.LC',
            'api_url': 'https://fc.lc/api',
            'requires_key': True
        }
    }

config = Config()
