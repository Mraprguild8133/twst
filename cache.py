import asyncio
from typing import Any, Optional
import aiocache
from aiocache import Cache, cached
from aiocache.serializers import JsonSerializer

class CacheManager:
    """High-performance caching system"""
    
    def __init__(self):
        self.cache = Cache(
            Cache.REDIS,
            endpoint="localhost",
            port=6379,
            serializer=JsonSerializer(),
            namespace="telegram_bot"
        )
    
    async def get_user_quota(self, user_id: int) -> int:
        """Get user upload quota with cache"""
        key = f"user_quota:{user_id}"
        return await self.cache.get(key, default=0)
    
    async def set_user_quota(self, user_id: int, count: int):
        """Set user upload quota with expiration"""
        key = f"user_quota:{user_id}"
        await self.cache.set(key, count, ttl=3600)  # 1 hour
    
    async def cache_image_url(self, image_hash: str, url: str):
        """Cache image URLs for fast retrieval"""
        await self.cache.set(f"image:{image_hash}", url, ttl=86400)  # 24 hours
    
    async def get_cached_image_url(self, image_hash: str) -> Optional[str]:
        """Get cached image URL"""
        return await self.cache.get(f"image:{image_hash}")

cache_manager = CacheManager()
