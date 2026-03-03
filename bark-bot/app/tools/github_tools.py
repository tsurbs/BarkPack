import os
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

from github import Github
from github import Auth

class GithubSearchArgs(BaseModel):
    query: str = Field(description="The search syntax to find issues (e.g. 'repo:my-org/my-repo is:issue is:open').")

class SearchGithubIssuesTool(BaseTool):
    name = "search_github_issues"
    description = "Search for GitHub issues across connected repositories."
    args_schema = GithubSearchArgs
    
    async def run(self, args: GithubSearchArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        token = os.getenv("GITHUB_TOKEN")
        if not token or token == "your_github_pat_here":
            return "Error: GITHUB_TOKEN is not set. Please add it to your .env file."
            
        try:
            auth = Auth.Token(token)
            g = Github(auth=auth)
            issues = g.search_issues(query=args.query)
            
            output = []
            for issue in issues[:10]: # Limit to top 10
                assignee = issue.assignee.login if issue.assignee else "None"
                output.append(f"- [{issue.state}] #{issue.number} {issue.title} (Assignee: {assignee})\n  URL: {issue.html_url}\n")
            
            g.close()
            if not output:
                 return f"No GitHub issues found for query: '{args.query}'"
            return f"Top 10 GitHub issues matching '{args.query}':\n" + "".join(output)
        except Exception as e:
            return f"Error communicating with GitHub: {str(e)}"

class GithubCreateIssueArgs(BaseModel):
    repository: str = Field(description="The repository name in 'owner/repo' format.")
    title: str = Field(description="The title of the issue.")
    body: str = Field(description="The markdown body describing the task.")
    assignees: list[str] = Field(description="List of GitHub usernames to assign to the issue.", default_factory=list)

class CreateGithubIssueTool(BaseTool):
    name = "create_github_issue"
    description = "Create a new issue in a GitHub repository."
    args_schema = GithubCreateIssueArgs
    
    async def run(self, args: GithubCreateIssueArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        token = os.getenv("GITHUB_TOKEN")
        if not token or token == "your_github_pat_here":
            return "Error: GITHUB_TOKEN is not set. Please add it to your .env file."
            
        try:
            auth = Auth.Token(token)
            g = Github(auth=auth)
            repo = g.get_repo(args.repository)
            
            kwargs = {
                "title": args.title,
                "body": args.body
            }
            if args.assignees:
                kwargs["assignees"] = args.assignees
                
            issue = repo.create_issue(**kwargs)
            g.close()
            return f"Successfully created GitHub issue #{issue.number}: '{issue.title}'\nURL: {issue.html_url}"
        except Exception as e:
            return f"Error creating GitHub issue in {args.repository}: {str(e)}"

class GithubUpdateStatusArgs(BaseModel):
    issue_id: str = Field(description="The global node ID or number of the GitHub issue.")
    project_id: str = Field(description="The global node ID of the GitHub Project.")
    status: str = Field(description="The new status column name (e.g., 'Todo', 'In Progress', 'Done').")

class UpdateGithubProjectStatusTool(BaseTool):
    name = "update_github_project_status"
    description = "Move an existing GitHub Issue to a new status column on a GitHub Project board."
    args_schema = GithubUpdateStatusArgs
    
    async def run(self, args: GithubUpdateStatusArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        # Note: Projects V2 requires complex GraphQL mutations which PyGithub doesn't natively support out-of-the-box in a simple way
        return f"Warning: GitHub Projects V2 updates require specialized GraphQL mutations. (Mock output for issue {args.issue_id} -> '{args.status}')"
