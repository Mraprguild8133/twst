import time
import asyncio
from typing import Dict, Tuple
from asyncio_throttle import Throttler

class RateLimiter:
    """Advanced rate limiting system"""
    
    def __init__(self):
        self.user_requests: Dict[int, list] = {}
        self.upload_throttler = Throttler(rate_limit=5, period=60)  # 5 uploads per minute
    
    async def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """Check if user exceeded rate limit"""
        now = time.time()
        window = settings.RATE_LIMIT_WINDOW
        
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id] 
            if now - req_time < window
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= settings.RATE_LIMIT_PER_USER:
            retry_after = int(window - (now - self.user_requests[user_id][0]))
            return False, retry_after
        
        self.user_requests[user_id].append(now)
        return True, 0

rate_limiter = RateLimiter()
