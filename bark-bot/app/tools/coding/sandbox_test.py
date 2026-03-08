import json
import sqlalchemy as sa
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxTestArgs(BaseModel):
    task_id: str
    command: str = Field(default="", description="Command to run. If empty, will attempt auto-detection.")

class SandboxTestTool(BaseTool):
    name = "sandbox_test"
    description = "Run tests in the sandbox. Automatically detects common test runners (Jest, Pytest, Cargo, Go) if no command is provided."
    args_schema = SandboxTestArgs

    async def run(self, args: SandboxTestArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        
        cmd = args.command
        if not cmd:
            # Auto-detection logic
            files_result = await sandbox.process.exec("ls -p")
            files = files_result.result.splitlines()
            
            if "package.json" in files:
                cmd = "npm test"
            elif "pytest.ini" in files or "requirements-dev.txt" in files or "conftest.py" in files:
                cmd = "pytest"
            elif "Cargo.toml" in files:
                cmd = "cargo test"
            elif "go.mod" in files:
                cmd = "go test ./..."
            else:
                return "Error: Could not auto-detect test runner. Please provide a command."

        result = await sandbox.process.exec(f"cd workspace/repo && {cmd}")
        
        output = result.result
        exit_code = result.exit_code
        
        if db:
            # Update task with latest test results
            await db.execute(sa.text("""
                UPDATE coding_tasks 
                SET test_results=:res, updated_at=now()
                WHERE task_id=:tid
            """), {
                "res": json.dumps({"command": cmd, "exit_code": exit_code, "output": output[:10000]}),
                "tid": args.task_id
            })
            await db.commit()

        status = "PASSED" if exit_code == 0 else "FAILED"
        return f"Tests {status} (Exit Code: {exit_code})\nCommand: {cmd}\nOutput:\n{output}"
