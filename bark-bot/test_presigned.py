import os
import boto3
import urllib.request
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
region = os.getenv("S3_REGION", "us-east-1")
bucket = os.getenv("S3_BUCKET_NAME", "barkbot")

s3 = boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name=region,
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'},
        request_checksum_calculation='when_required'
    )
)

# 1. Upload
print("Uploading file via API...")
with open("test.txt", "w") as f:
    f.write("hello world from presigned test")
with open("test.txt", "rb") as f:
    s3.put_object(Bucket=bucket, Key="test_presigned.txt", Body=f.read())

# 2. Generate Presigned URL
print("Generating URL...")
url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': bucket, 'Key': 'test_presigned.txt'},
    ExpiresIn=3600
)

print(f"URL: {url}")

# 3. Test Download
print("Downloading from URL...")
try:
    response = urllib.request.urlopen(url)
    print("Content:", response.read().decode('utf-8'))
except Exception as e:
    print("Error:", str(e))
