import asyncio
from io import BytesIO
from PIL import Image, ImageOps
import aiohttp
import ujson as json

class AdvancedImageProcessor:
    """High-performance image processing with optimization"""
    
    @staticmethod
    async def optimize_image(image_data: BytesIO, max_size: tuple = (1920, 1080)) -> BytesIO:
        """Optimize image for web with compression"""
        try:
            with Image.open(image_data) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Optimize and compress
                output = BytesIO()
                img.save(
                    output,
                    format='JPEG',
                    quality=settings.COMPRESSION_QUALITY,
                    optimize=True
                )
                output.seek(0)
                return output
        except Exception as e:
            raise Exception(f"Image optimization failed: {str(e)}")
    
    @staticmethod
    async def generate_image_hash(image_data: BytesIO) -> str:
        """Generate hash for duplicate detection"""
        import hashlib
        return hashlib.md5(image_data.getvalue()).hexdigest()

image_processor = AdvancedImageProcessor()
