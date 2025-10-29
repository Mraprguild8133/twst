import time
from typing import Callable

class Progress:
    def __init__(self, client, message, file_type="file"):
        self.client = client
        self.message = message
        self.file_type = file_type
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.previous = 0

    async def progress_callback(self, bytes_amount):
        """Progress callback for upload/download operations"""
        current_time = time.time()
        
        # Throttle updates to prevent spam
        if current_time - self.last_update_time < 2 and bytes_amount - self.previous < 1024 * 1024:
            return
        
        try:
            # Calculate progress
            speed = (bytes_amount - self.previous) / (current_time - self.last_update_time) if current_time > self.last_update_time else 0
            elapsed_time = current_time - self.start_time
            estimated_total_time = elapsed_time * (self.total_size / bytes_amount) if bytes_amount > 0 else 0
            remaining_time = estimated_total_time - elapsed_time
            
            # Format sizes
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"
            
            # Format time
            def format_time(seconds):
                if seconds < 60:
                    return f"{seconds:.0f}s"
                elif seconds < 3600:
                    return f"{seconds/60:.0f}m {seconds%60:.0f}s"
                else:
                    return f"{seconds/3600:.0f}h {seconds%3600/60:.0f}m"
            
            progress_text = (
                f"📤 **Uploading {self.file_type}**\n\n"
                f"📊 **Progress:** {format_size(bytes_amount)} / {format_size(self.total_size)}\n"
                f"🚀 **Speed:** {format_size(speed)}/s\n"
                f"⏱️ **Time Left:** {format_time(remaining_time)}\n"
                f"🕒 **Elapsed:** {format_time(elapsed_time)}"
            )
            
            await self.message.edit_text(progress_text)
            
            self.last_update_time = current_time
            self.previous = bytes_amount
            
        except Exception as e:
            # Ignore message editing errors during progress updates
            pass

    def set_total_size(self, total_size):
        self.total_size = total_size
