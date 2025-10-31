# torrent_services.py
import aiohttp
import asyncio
import json
import time
from typing import Optional, Dict, Any
from config import config

class TorrentService:
    """Base class for torrent services"""
    
    async def download_torrent(self, torrent_link: str, message) -> Optional[str]:
        """Download torrent and return local file path"""
        raise NotImplementedError

class RealDebridService(TorrentService):
    """Real-Debrid integration"""
    
    def __init__(self):
        self.api_key = config.REAL_DEBRID_API_KEY
        self.base_url = "https://api.real-debrid.com/rest/1.0"
        
    async def download_torrent(self, torrent_link: str, message) -> Optional[str]:
        if not self.api_key:
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            async with aiohttp.ClientSession() as session:
                # Add torrent to Real-Debrid
                add_data = {"magnet": torrent_link}
                async with session.post(f"{self.base_url}/torrents/addMagnet", 
                                      data=add_data, headers=headers) as resp:
                    if resp.status != 201:
                        return None
                    torrent_info = await resp.json()
                    torrent_id = torrent_info['id']
                
                # Select all files (you can modify this to select specific files)
                async with session.post(f"{self.base_url}/torrents/selectFiles/{torrent_id}", 
                                      data={"files": "all"}, headers=headers) as resp:
                    if resp.status != 204:
                        return None
                
                # Wait for download to complete
                await message.edit_text("📥 Downloading via Real-Debrid...")
                for _ in range(60):  # Wait up to 5 minutes
                    await asyncio.sleep(5)
                    
                    async with session.get(f"{self.base_url}/torrents/info/{torrent_id}", 
                                         headers=headers) as resp:
                        if resp.status == 200:
                            info = await resp.json()
                            if info['status'] == 'downloaded':
                                # Get download link
                                if info['links']:
                                    download_link = info['links'][0]
                                    # Unrestrict the link
                                    unrestrict_data = {"link": download_link}
                                    async with session.post(f"{self.base_url}/unrestrict/link", 
                                                          data=unrestrict_data, headers=headers) as uresp:
                                        if uresp.status == 200:
                                            result = await uresp.json()
                                            return result['download']
                    await message.edit_text(f"🔄 Download progress: {info.get('progress', 0)}%")
                
                return None
                
        except Exception as e:
            print(f"Real-Debrid error: {e}")
            return None

class PremiumizeService(TorrentService):
    """Premiumize.me integration"""
    
    def __init__(self):
        self.api_key = config.PREMIUMIZE_API_KEY
        self.base_url = "https://www.premiumize.me/api"
        
    async def download_torrent(self, torrent_link: str, message) -> Optional[str]:
        if not self.api_key:
            return None
            
        try:
            async with aiohttp.ClientSession() as session:
                # Create transfer
                params = {
                    "apikey": self.api_key,
                    "src": torrent_link,
                    "folder_id": None
                }
                async with session.post(f"{self.base_url}/transfer/create", params=params) as resp:
                    if resp.status != 200:
                        return None
                    result = await resp.json()
                    transfer_id = result['id']
                
                # Wait for completion
                await message.edit_text("📥 Downloading via Premiumize...")
                for _ in range(60):
                    await asyncio.sleep(5)
                    
                    params = {"apikey": self.api_key}
                    async with session.get(f"{self.base_url}/transfer/list", params=params) as resp:
                        if resp.status == 200:
                            transfers = await resp.json()
                            transfer = next((t for t in transfers['transfers'] if t['id'] == transfer_id), None)
                            if transfer and transfer['status'] == 'finished':
                                # Get download link
                                file_id = transfer['file_id']
                                params = {"apikey": self.api_key, "id": file_id}
                                async with session.get(f"{self.base_url}/item/details", params=params) as resp:
                                    if resp.status == 200:
                                        item_info = await resp.json()
                                        return item_info['content'][0]['link']
                    await message.edit_text(f"🔄 Download progress: {transfer.get('progress', 0)}%")
                
                return None
                
        except Exception as e:
            print(f"Premiumize error: {e}")
            return None

class MockTorrentService(TorrentService):
    """Mock service for testing - creates dummy files"""
    
    async def download_torrent(self, torrent_link: str, message) -> Optional[str]:
        """Create a dummy file for testing"""
        import tempfile
        import os
        
        try:
            await message.edit_text("📥 Simulating torrent download...")
            await asyncio.sleep(2)
            
            # Create temp file
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, f"downloaded_file_{int(time.time())}.mp4")
            
            # Create a dummy file (50MB for testing)
            file_size = 50 * 1024 * 1024
            with open(file_path, 'wb') as f:
                f.seek(file_size - 1)
                f.write(b'\0')
            
            await message.edit_text("✅ Download simulation complete!")
            return file_path
            
        except Exception as e:
            print(f"Mock service error: {e}")
            return None

class TorrentServiceManager:
    """Manages multiple torrent services"""
    
    def __init__(self):
        self.services = [
            RealDebridService(),
            PremiumizeService(),
            MockTorrentService()  # Fallback for testing
        ]
    
    async def download_torrent(self, torrent_link: str, message) -> Optional[str]:
        """Try all available services until one works"""
        for service in self.services:
            await message.edit_text(f"🔄 Trying {service.__class__.__name__}...")
            result = await service.download_torrent(torrent_link, message)
            if result:
                return result
        return None
