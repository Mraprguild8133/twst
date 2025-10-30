# Add this test script to debug_wasabi.py
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def test_wasabi_connection():
    try:
        # Test configuration
        config = {
            'endpoint_url': f"https://s3.{os.getenv('WASABI_REGION')}.wasabisys.com",
            'aws_access_key_id': os.getenv('WASABI_ACCESS_KEY'),
            'aws_secret_access_key': os.getenv('WASABI_SECRET_KEY'),
            'region_name': os.getenv('WASABI_REGION')
        }
        
        print("🔍 Testing Wasabi Configuration...")
        print(f"Endpoint: {config['endpoint_url']}")
        print(f"Access Key: {config['aws_access_key_id'][:10]}...")
        print(f"Secret Key: {config['aws_secret_access_key'][:10]}...")
        print(f"Bucket: {os.getenv('WASABI_BUCKET')}")
        print(f"Region: {config['region_name']}")
        
        # Test connection
        s3 = boto3.client('s3', **config)
        
        # List buckets to test credentials
        response = s3.list_buckets()
        print("✅ Successfully connected to Wasabi!")
        print(f"Available buckets: {[b['Name'] for b in response['Buckets']]}")
        
        # Test specific bucket access
        bucket = os.getenv('WASABI_BUCKET')
        try:
            s3.head_bucket(Bucket=bucket)
            print(f"✅ Bucket '{bucket}' is accessible")
        except Exception as e:
            print(f"❌ Cannot access bucket '{bucket}': {e}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_wasabi_connection()
