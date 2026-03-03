import os
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

class WriteFileArgs(BaseModel):
    filepath: str = Field(description="The relative path (from the workspace root) where the file should be written.")
    content: str = Field(description="The string content to write into the file.")

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write text content to a file in the workspace directory."
    args_schema = WriteFileArgs
    
    async def run(self, args: WriteFileArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        try:
            workspace_dir = os.path.join(os.getcwd(), "workspace")
            os.makedirs(workspace_dir, exist_ok=True)
            
            full_path = os.path.abspath(os.path.join(workspace_dir, args.filepath))
            
            # Basic path traversal protection
            if not full_path.startswith(workspace_dir):
                return "Error: Cannot write outside of the workspace directory."
                
            # Create subdirectories if they don't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(args.content)
                
            return f"Successfully wrote to {args.filepath}"
        except Exception as e:
            return f"Error writing file {args.filepath}: {str(e)}"
