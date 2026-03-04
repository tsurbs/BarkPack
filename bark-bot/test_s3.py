import os
import boto3
from dotenv import load_dotenv
from botocore.client import Config

load_dotenv()

endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")

s3 = boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
)

print('Using key:', os.getenv("S3_ACCESS_KEY_ID"))
print('Endpoint:', endpoint_url)

url = s3.generate_presigned_url('list_buckets')
print('Presigned URL:', url)
import urllib.request
try:
    print(urllib.request.urlopen(url).read().decode('utf-8'))
except Exception as e:
    print('HTTP Error:', e.read().decode('utf-8') if hasattr(e, 'read') else str(e))
