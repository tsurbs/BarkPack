"""
Shared S3 client configuration.
Centralizes boto3 client creation from environment variables.
"""
import os
import boto3
from botocore.client import Config


def get_s3_client():
    """Create and return a configured boto3 S3 client."""
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    aws_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
    region_name = os.getenv("S3_REGION", "us-east-1")

    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
        config=Config(
            signature_version='s3v4',
            region_name=region_name,
            s3={'addressing_style': 'path'},
            request_checksum_calculation='when_required'
        )
    )


def get_bucket_name() -> str:
    """Return the configured S3 bucket name."""
    return os.getenv("S3_BUCKET_NAME", "barkbot")


def get_skills_prefix() -> str:
    """Return the S3 key prefix for skill storage."""
    return os.getenv("S3_SKILLS_PREFIX", "skills/")
