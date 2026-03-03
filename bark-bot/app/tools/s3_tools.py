import os
import boto3
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
import mimetypes

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
            
        endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:3900")
        aws_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
        bucket_name = "barkbot-public"
        
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
                region_name='garage'
            )
            s3_client.upload_file(args.file_path, bucket_name, object_name, ExtraArgs=extra_args)
            
            # Use Garage's Virtual-hosted style url for the web endpoint
            # Fallback to localhost if S3_WEB_URL is not provided
            base_web_url = os.getenv("S3_WEB_URL", f"http://{bucket_name}.web.localhost:3902")
            public_url = f"{base_web_url.rstrip('/')}/{object_name}"
            
            return f"Successfully uploaded file to S3.\nPublic URL: {public_url}"
            
        try:
            return await asyncio.to_thread(_upload)
        except Exception as e:
            return f"Error uploading to S3: {str(e)}"
