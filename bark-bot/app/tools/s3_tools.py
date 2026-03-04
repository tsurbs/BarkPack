import os
import boto3
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
import mimetypes
from botocore.client import Config

class UploadToS3Args(BaseModel):
    file_path: str = Field(description="The absolute path to the local file to upload.")
    object_name: str = Field(description="The destination name for the file in the bucket (e.g., 'images/plot.png').", default=None)

class UploadToS3Tool(BaseTool):
    name = "upload_to_s3"
    description = "Upload a local file to the public S3 bucket and return a shareable public link."
    args_schema = UploadToS3Args
    
    async def run(self, args: UploadToS3Args, user: User, db: Optional[AsyncSession] = None) -> str:
        if not os.path.exists(args.file_path):
            return f"Error: Local file '{args.file_path}' does not exist."
            
        endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
        aws_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("S3_BUCKET_NAME", "barkbot")
        region_name = os.getenv("S3_REGION", "us-east-1")
        
        os.environ["AWS_DEFAULT_REGION"] = region_name
        os.environ["AWS_REGION"] = region_name
        
        if not aws_access_key_id or not aws_secret_access_key:
            return "Error: S3 credentials are not configured in the environment."
            
        object_name = args.object_name or os.path.basename(args.file_path)
        
        content_type, _ = mimetypes.guess_type(args.file_path)
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        def _upload():
            s3_client = boto3.client(
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
            
            with open(args.file_path, "rb") as f:
                s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=f.read(), **extra_args)
            
            # Generate a pre-signed URL valid for 7 days
            public_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_name},
                ExpiresIn=604800  # 7 days in seconds
            )
            
            return f"Successfully uploaded file to S3.\nPre-signed URL (Valid for 7 days, query params are very important): {public_url}"
            
        try:
            return await asyncio.to_thread(_upload)
        except Exception as e:
            return f"Error uploading to S3: {str(e)}"

class ListS3BucketArgs(BaseModel):
    prefix: str = Field(description="Optional prefix to filter the list of objects (e.g., 'images/').", default="")

class ListS3BucketTool(BaseTool):
    name = "list_s3_bucket"
    description = "List the contents of the public S3 bucket, returning object names, sizes, and their shareable public URLs.\n\nQuery params are very important."
    args_schema = ListS3BucketArgs
    
    async def run(self, args: ListS3BucketArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
        aws_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("S3_BUCKET_NAME", "barkbot")
        region_name = os.getenv("S3_REGION", "us-east-1")
        
        os.environ["AWS_DEFAULT_REGION"] = region_name
        os.environ["AWS_REGION"] = region_name
        
        if not aws_access_key_id or not aws_secret_access_key:
            return "Error: S3 credentials are not configured in the environment."

        def _list_objects():
            s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name,
                config=Config(
                    signature_version='s3v4',
                    region_name=region_name,
                    s3={'addressing_style': 'path'}
                )
            )
            
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=args.prefix)
            
            if 'Contents' not in response or not response['Contents']:
                return "The bucket is empty or no files match the given prefix."
            
            lines = [f"Contents of bucket '{bucket_name}' (Prefix: '{args.prefix}'):"]
            for obj in response['Contents']:
                name = obj['Key']
                size_kb = obj['Size'] / 1024
                date = obj['LastModified'].strftime("%Y-%m-%d %H:%M:%S")
                
                # Generate a pre-signed URL valid for 7 days
                public_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': name},
                    ExpiresIn=604800  # 7 days in seconds
                )
                     
                lines.append(f"- {name} ({size_kb:.1f} KB, Modified {date})\n  Link: {public_url}")
            
            return "\n".join(lines)

        try:
            return await asyncio.to_thread(_list_objects)
        except Exception as e:
            return f"Error listing S3 bucket: {str(e)}"
