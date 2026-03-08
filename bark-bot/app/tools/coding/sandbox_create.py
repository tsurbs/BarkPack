import os
import uuid
import sqlalchemy as sa
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import get_client, register_sandbox, SNAPSHOT

class SandboxCreateArgs(BaseModel):
    task_id: str = Field(
        default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}",
        description="Unique task identifier. Auto-generated if omitted."
    )
    task_description: str = Field(..., description="Full description of the coding task")
    repo_url: str = Field(..., description="Git HTTPS URL of the repo to clone")
    branch: str = Field(default="main", description="Branch to clone")
    git_username: str = Field(default="")
    git_token: str = Field(default="", description="PAT for private repos")

class SandboxCreateTool(BaseTool):
    name = "sandbox_create"
    description = (
        "Create a Daytona sandbox with a relevant name and clone a git repo into it. "
        "Returns the task_id. Call this once at the start of every coding task."
    )
    args_schema = SandboxCreateArgs

    async def run(self, args: SandboxCreateArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        client = get_client()

        from daytona_sdk import CreateSandboxFromSnapshotParams
        
        # Determine a relevant name for the sandbox
        # Example: barkbot-repo-branch-taskid
        repo_name = args.repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        
        sandbox_name = f"bb-{repo_name}-{args.branch}-{args.task_id}"
        # Daytona names must be alphanumeric/dashes
        sandbox_name = "".join(c if c.isalnum() or c == "-" else "-" for c in sandbox_name).lower()
        sandbox_name = sandbox_name[:60] # Limit length

        # Fallback to GITHUB_TOKEN from env
        git_token = args.git_token or os.getenv("GITHUB_TOKEN", "")
        env_vars = {"TASK_ID": args.task_id}
        if git_token:
            env_vars["GITHUB_TOKEN"] = git_token

        params = CreateSandboxFromSnapshotParams(
            snapshot=SNAPSHOT, 
            name=sandbox_name,
            env_vars=env_vars,
            labels={"task_id": args.task_id}
        )
        sandbox = await client.create(params)

        clone_kwargs = dict(url=args.repo_url, path="workspace/repo", branch=args.branch)
        if git_token:
            username = args.git_username or "git"
            clone_kwargs.update(username=username, password=git_token)
        
        await sandbox.git.clone(**clone_kwargs)

        if git_token:
            await sandbox.process.exec(
                f'git config --global url."https://{git_token}@github.com/".insteadOf "https://github.com/"'
            )

        await register_sandbox(args.task_id, sandbox)

        if db:
            await db.execute(sa.text("""
                INSERT INTO coding_tasks
                  (id, task_id, status, task_description, repo_url, branch, sandbox_id, created_at, updated_at)
                VALUES
                  (:uid, :task_id, 'running', :desc, :repo_url, :branch, :sandbox_id, now(), now())
            """), {
                "uid": str(uuid.uuid4()),
                "task_id": args.task_id, 
                "desc": args.task_description,
                "repo_url": args.repo_url, 
                "branch": args.branch,
                "sandbox_id": sandbox.id,
            })
            await db.commit()

        return (
            f"Sandbox {sandbox_name!r} ready. task_id={args.task_id}\n"
            f"Repo cloned: {args.repo_url} @ {args.branch}\n"
            f"Workspace: workspace/repo"
        )
