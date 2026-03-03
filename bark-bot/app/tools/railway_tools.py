import subprocess
import os
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

class RailwayDeployArgs(BaseModel):
    service_name: str = Field(description="The name of the Railway service to deploy to.")
    environment: str = Field(description="The Railway environment to deploy to (e.g. 'production', 'staging').", default="production")
    command_args: str = Field(description="Additional arguments for the railway up command.", default="")

class RailwayDeployTool(BaseTool):
    name = "railway_deploy"
    description = "Deploy the current repository in the workspace to Railway using the Railway CLI."
    args_schema = RailwayDeployArgs
    
    async def run(self, args: RailwayDeployArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        try:
            workspace_dir = os.path.join(os.getcwd(), "workspace")
            
            # This requires 'railway' CLI to be installed and authenticated on the host machine.
            # `railway up --service <name> --environment <env>`
            cmd = f"railway up --service {args.service_name} --environment {args.environment} {args.command_args}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=300 # Deployments can take a few minutes
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
                
            if result.returncode == 0:
                 return f"Successfully initiated deployment for {args.service_name} to {args.environment}.\nOutput:\n{output}"
            else:
                 return f"Failed to deploy to Railway. Return code: {result.returncode}\nOutput:\n{output}"
                 
        except subprocess.TimeoutExpired:
            return "Error: Railway deployment timed out after 5 minutes."
        except Exception as e:
            return f"Error executing railway deploy: {str(e)}"
