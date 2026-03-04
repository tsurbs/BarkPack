from typing import Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


class AttachFileArgs(BaseModel):
    file_path: str = Field(description="The absolute local file path of the file to attach (e.g. '/tmp/chart.png').")
    filename: str = Field(description="The display filename for the attachment (e.g. 'chart.png').", default=None)


class AttachFileTool(BaseTool):
    name = "attach_file"
    description = (
        "Attach a local file to your response so it appears as a native file upload in the user's chat surface (e.g. Slack). "
        "Provide the absolute local file path. You can call this tool multiple times to attach multiple files."
    )
    args_schema = AttachFileArgs

    async def run(self, args: AttachFileArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        import os
        if not os.path.exists(args.file_path):
            return f"Error: File '{args.file_path}' does not exist."
        filename = args.filename or os.path.basename(args.file_path)
        return f"__ATTACHMENT__|||{args.file_path}|||{filename}"
