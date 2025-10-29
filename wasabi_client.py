import boto3
import asyncio
import aiofiles
from botocore.config import Config as BotoConfig
from config import Config
from progress import Progress

class WasabiClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.WASABI_ACCESS_KEY,
            aws_secret_access_key=Config.WASABI_SECRET_KEY,
            endpoint_url=Config.WASABI_ENDPOINT,
            region_name=Config.WASABI_REGION,
            config=BotoConfig(
                s3={'addressing_style': 'virtual'},
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
        )
        self.bucket = Config.WASABI_BUCKET

    async def upload_file(self, file_path, object_name, progress_callback=None):
        """Upload file to Wasabi with progress tracking"""
        try:
            extra_args = {
                'ACL': 'public-read',
                'ContentType': self._get_content_type(object_name)
            }
            
            if progress_callback:
                self.s3_client.upload_file(
                    file_path, self.bucket, object_name,
                    ExtraArgs=extra_args,
                    Callback=progress_callback
                )
            else:
                self.s3_client.upload_file(
                    file_path, self.bucket, object_name,
                    ExtraArgs=extra_args
                )
            
            # Generate public URL
            url = f"https://{self.bucket}.s3.{Config.WASABI_REGION}.wasabisys.com/{object_name}"
            return url
        except Exception as e:
            raise Exception(f"Upload failed: {str(e)}")

    async def download_file(self, object_name, file_path, progress_callback=None):
        """Download file from Wasabi with progress tracking"""
        try:
            if progress_callback:
                self.s3_client.download_file(
                    self.bucket, object_name, file_path,
                    Callback=progress_callback
                )
            else:
                self.s3_client.download_file(
                    self.bucket, object_name, file_path
                )
            return file_path
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    async def generate_presigned_url(self, object_name, expires_in=3600):
        """Generate presigned URL for temporary access"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_name},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            raise Exception(f"URL generation failed: {str(e)}")

    def _get_content_type(self, filename):
        """Get content type based on file extension"""
        ext = filename.lower().split('.')[-1]
        content_types = {
            'mp4': 'video/mp4',
            'mkv': 'video/x-matroska',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mp3': 'audio/mpeg',
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
        }
        return content_types.get(ext, 'application/octet-stream')

    async def file_exists(self, object_name):
        """Check if file exists in Wasabi"""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except:
            return False

    async def delete_file(self, object_name):
        """Delete file from Wasabi"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_name)
            return True
        except Exception as e:
            raise Exception(f"Delete failed: {str(e)}")
