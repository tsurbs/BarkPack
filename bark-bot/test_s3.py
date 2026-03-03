import os
import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    's3',
    endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:3900"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name='garage'
)

# List objects
response = s3.list_objects_v2(Bucket='barkbot-public')
print("Objects in bucket:")
if 'Contents' in response:
    for obj in response['Contents']:
        print(f"- {obj['Key']} (Size: {obj['Size']})")
else:
    print("Bucket is empty or not found.")
