#!/bin/bash
# Setup script for local RustFS development instance.
# Run after `docker compose up -d` to create the initial bucket.

set -e

ENDPOINT="${S3_ENDPOINT_URL:-http://localhost:9000}"
ACCESS_KEY="${S3_ACCESS_KEY_ID:-rustfsadmin}"
SECRET_KEY="${S3_SECRET_ACCESS_KEY:-rustfsadmin}"
BUCKET="${S3_BUCKET_NAME:-barkbot}"

echo "Waiting for RustFS to be ready..."
until curl -sf "$ENDPOINT/minio/health/live" > /dev/null 2>&1; do
    sleep 1
done

echo "Creating bucket '$BUCKET'..."
python3 -c "
import boto3
from botocore.client import Config

s3 = boto3.client(
    's3',
    endpoint_url='$ENDPOINT',
    aws_access_key_id='$ACCESS_KEY',
    aws_secret_access_key='$SECRET_KEY',
    region_name='us-east-1',
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
)

try:
    s3.create_bucket(Bucket='$BUCKET')
    print('Bucket created successfully.')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print('Bucket already exists.')
except Exception as e:
    print(f'Note: {e}')
"

echo "Setup complete."
