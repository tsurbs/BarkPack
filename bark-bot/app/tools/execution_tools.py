import subprocess
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

class ExecuteBashArgs(BaseModel):
    command: str = Field(description="The bash command to execute.")

class ExecuteBashTool(BaseTool):
    name = "execute_bash"
    description = "Execute a bash command in the local workspace directory. Use this to run git commands, install dependencies, or inspect files."
    args_schema = ExecuteBashArgs
    
    async def run(self, args: ExecuteBashArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        try:
            # We run this in the 'workspace/' directory for safety
            import os
            workspace_dir = os.path.join(os.getcwd(), "workspace")
            os.makedirs(workspace_dir, exist_ok=True)
            
            result = subprocess.run(
                args.command,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=60 # Prevent hanging commands
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
                
            return output if output else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            return f"Error executing bash command: {str(e)}"

class ExecutePythonArgs(BaseModel):
    script: str = Field(description="The Python script content to execute.")

class ExecutePythonScriptTool(BaseTool):
    name = "execute_python_script"
    description = "Write and execute a Python script locally. Returns the stdout output. Used for data analysis and quick calculations."
    args_schema = ExecutePythonArgs
    
    async def run(self, args: ExecutePythonArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        import tempfile
        import os
        
        workspace_dir = os.path.join(os.getcwd(), "workspace")
        os.makedirs(workspace_dir, exist_ok=True)
            
        try:
            # Create a temporary file to hold the script within the workspace
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir=workspace_dir, delete=False) as temp_file:
                temp_file.write(args.script)
                temp_path = temp_file.name

            # Execute it
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Clean up
            os.unlink(temp_path)
            
            output = result.stdout
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
                
            return output if output else "Script executed successfully with no output."
        except subprocess.TimeoutExpired:
            if 'temp_path' in locals(): os.unlink(temp_path)
            return "Error: Python script timed out after 120 seconds."
        except Exception as e:
            if 'temp_path' in locals(): os.unlink(temp_path)
            return f"Error executing python script: {str(e)}"
