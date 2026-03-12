import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, create_model

from app.tools.base import BaseTool
from app.db.models import DBTool
from app.db.session import AsyncSessionLocal as async_session
import os

logger = logging.getLogger(__name__)

# Native Tool Imports
from app.tools.core_tools import ReadFileTool, SearchTool
from app.tools.memory_tools import CreateAgentPostTool, SearchAgentPostsTool, ListPastConversationsTool, ReadConversationTool
from app.tools.execution_tools import ExecuteBashTool, ExecutePythonScriptTool
from app.tools.file_tools import WriteFileTool
from app.tools.railway_tools import RailwayDeployTool
from app.tools.knowledge_tools import SearchNotionTool, ReadNotionPageTool, TavilySearchTool, FirecrawlTool
from app.tools.summarization_tools import SummarizeConversationTool, UpdateUserProfileTool
from app.tools.github_tools import SearchGithubIssuesTool, CreateGithubIssueTool, UpdateGithubProjectStatusTool, CreatePullRequestTool
from app.tools.google_workspace_tools import (
    ReadGmailMessagesTool, SendGmailTool, DraftGmailTool, CreateCalendarEventTool, FindCalendarFreeBusyTool,
    SearchDriveFilesTool, ModifyDrivePermissionsTool, CreateGoogleDocTool, ReadGoogleDocTool,
    UpdateGoogleSheetTool, ReadGoogleSheetTool, SubscribeWorkspaceEventsTool, ManageCloudIdentityGroupsTool
)
from app.tools.s3_tools import UploadToS3Tool, ListS3BucketTool
from app.tools.image_tools import GenerateImageTool
from app.tools.pdf_tools import GeneratePDFTool, GeneratePDFWithURLTool
from app.tools.slack_tools import SendSlackMessageTool, ListSlackChannelsTool
from app.tools.attachment_tools import AttachFileTool
from app.tools.news_tools import SearchNewsTool, GetTopHeadlinesTool
from app.tools.coding.sandbox_bash import SandboxBashTool
from app.tools.coding.sandbox_read import SandboxReadTool
from app.tools.coding.sandbox_write import SandboxWriteTool
from app.tools.coding.sandbox_edit import SandboxEditTool
from app.tools.coding.sandbox_glob import SandboxGlobTool
from app.tools.coding.sandbox_grep import SandboxGrepTool
from app.tools.coding.sandbox_list import SandboxListTool
from app.tools.coding.sandbox_git_status import SandboxGitStatusTool
from app.tools.coding.sandbox_git_commit import SandboxGitCommitTool
from app.tools.coding.sandbox_git_push import SandboxGitPushTool
from app.tools.coding.sandbox_test import SandboxTestTool
from app.tools.coding.sandbox_diff import SandboxDiffTool
from app.tools.coding.sandbox_create import SandboxCreateTool
from app.tools.coding.sandbox_release import SandboxReleaseTool
from app.tools.coding.sandbox_resume import SandboxResumeTool
from app.tools.coding.sandbox_start import SandboxStartTool
from app.tools.coding.sandbox_list_running import SandboxListRunningTool

# Map of statically known native tools
NATIVE_TOOLS = {
    t.name: t for t in [
        ReadFileTool(), SearchTool(), CreateAgentPostTool(), SearchAgentPostsTool(),
        ListPastConversationsTool(), ReadConversationTool(), ExecuteBashTool(),
        ExecutePythonScriptTool(), WriteFileTool(), RailwayDeployTool(),
        SearchNotionTool(), ReadNotionPageTool(), TavilySearchTool(),
        FirecrawlTool(), SummarizeConversationTool(), UpdateUserProfileTool(),
        SearchGithubIssuesTool(), CreateGithubIssueTool(), UpdateGithubProjectStatusTool(), CreatePullRequestTool(),
        ReadGmailMessagesTool(), SendGmailTool(), DraftGmailTool(), CreateCalendarEventTool(),
        FindCalendarFreeBusyTool(), SearchDriveFilesTool(), ModifyDrivePermissionsTool(),
        CreateGoogleDocTool(), ReadGoogleDocTool(), UpdateGoogleSheetTool(),
        ReadGoogleSheetTool(), SubscribeWorkspaceEventsTool(), ManageCloudIdentityGroupsTool(),
        UploadToS3Tool(), ListS3BucketTool(), SendSlackMessageTool(),
        ListSlackChannelsTool(), AttachFileTool(), GenerateImageTool(),
        SearchNewsTool(), GetTopHeadlinesTool(),
        GeneratePDFTool(), GeneratePDFWithURLTool(),
        SandboxBashTool(), SandboxReadTool(), SandboxWriteTool(), SandboxEditTool(),
        SandboxGlobTool(), SandboxGrepTool(), SandboxListTool(), SandboxGitStatusTool(),
        SandboxGitCommitTool(), SandboxGitPushTool(), SandboxTestTool(), SandboxDiffTool(),
        SandboxCreateTool(), SandboxReleaseTool(), SandboxResumeTool(), SandboxStartTool(), SandboxListRunningTool()
    ]
}

# In-memory cache for loaded tools
_TOOL_CACHE = {}  # Tool Name -> BaseTool Instance
_MCP_CONTEXTS = {} # Tool ID -> MCP context blocks

def _compile_python_tool(name: str, description: str, content: str) -> BaseTool:
    local_vars = {}
    # Provide commonly used imports to the eval context to make script writing easier
    eval_globals = {
        "BaseModel": BaseModel,
        "AsyncSession": AsyncSession,
        "Any": Any,
        "Optional": Optional,
        "Dict": Dict,
        "List": List,
        "json": json,
        "asyncio": asyncio,
    }
    
    try:
        exec(content, eval_globals, local_vars)
    except Exception as e:
        raise ValueError(f"Failed to compile python code: {e}")

    ArgsSchema = local_vars.get("Args", None)
    run_func = local_vars.get("run", None)

    if not ArgsSchema or not issubclass(ArgsSchema, BaseModel):
        raise ValueError(f"Python tool {name} must define an 'Args' class inheriting from pydantic.BaseModel")
    if not run_func or not callable(run_func):
        raise ValueError(f"Python tool {name} must define an async 'run(self, args, user, db)' function")

    class DynamicPythonTool(BaseTool):
        def __init__(self):
            self.name = name
            self.description = description
            self.args_schema = ArgsSchema

        async def run(self, args: BaseModel, user, db: Optional[AsyncSession] = None) -> Any:
            return await run_func(self, args, user, db)

    return DynamicPythonTool()

async def ensure_tools_initialized():
    """Sync all NATIVE_TOOLS to the database on startup."""
    async with async_session() as db:
        result = await db.execute(select(DBTool).where(DBTool.tool_type == "native"))
        existing_native = {t.name: t for t in result.scalars().all()}

        for name, tool in NATIVE_TOOLS.items():
            if name not in existing_native:
                new_tool = DBTool(
                    name=name,
                    description=tool.description,
                    tool_type="native",
                    content="{}"
                )
                db.add(new_tool)
        await db.commit()
    logger.info("Native tools synced to database.")

async def build_mcp_tools(tool_id: str, content: str) -> List[BaseTool]:
    """Connect to an MCP server and wrap its tools."""
    from mcp import StdioServerParameters, ClientSession
    from mcp.client.stdio import stdio_client

    try:
        config = json.loads(content)
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})
    except Exception as e:
        logger.error(f"Failed to parse MCP config for {tool_id}: {e}")
        return []

    server_params = StdioServerParameters(command=command, args=args, env={**os.environ, **env})
    
    # Needs to be stored persistently so connection acts properly
    # Implementation detail: Because stdio_client() returns async context managers,
    # we need a tricky way to keep them alive if we want persistent connections...
    # For now, MVP: we connect dynamically each time.
    # Note: In a production setting we'd want to maintain an active process pool.
    class MCPDynamicTool(BaseTool):
        def __init__(self, mcp_name, mcp_desc, schema_dict, s_params):
            self.name = mcp_name
            self.description = mcp_desc
            self.server_params = s_params
            
            # Build Pydantic model for schema_dict
            props = schema_dict.get("properties", {})
            required = schema_dict.get("required", [])
            fields = {}
            for k, v in props.items():
                fields[k] = (Any, ... if k in required else None)
            
            if not fields:
                self.args_schema = create_model(f"MCPArgs_{self.name}")
            else:
                self.args_schema = create_model(f"MCPArgs_{self.name}", **fields)

        async def run(self, args: BaseModel, user, db: Optional[AsyncSession] = None) -> Any:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(self.name, arguments=args.model_dump())
                    return str(result.content)

    mcp_tools = []
    try:
        import os
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                discovery = await session.list_tools()
                for t in discovery.tools:
                    mcp_tools.append(MCPDynamicTool(t.name, t.description or "MCP Ext Tool", t.inputSchema, server_params))
    except Exception as e:
        logger.error(f"Failed to discover MCP tools for server {command}: {e}")
        
    return mcp_tools

async def get_all_available_tools(db: AsyncSession) -> Dict[str, BaseTool]:
    """
    Fetch all tools from the DB and return the instantiated BaseTool dictionary.
    """
    result = await db.execute(select(DBTool))
    db_tools = result.scalars().all()

    available = {}
    
    for dt in db_tools:
        # Cache check? MVP: Always rebuild python, but MCP connects maybe slow.
        try:
            if dt.tool_type == "native":
                if dt.name in NATIVE_TOOLS:
                    available[dt.name] = NATIVE_TOOLS[dt.name]
            elif dt.tool_type == "python":
                tool = _compile_python_tool(dt.name, dt.description, dt.content)
                available[tool.name] = tool
            elif dt.tool_type == "mcp":
                # Build one connection block per MCP row to find its tools
                m_tools = await build_mcp_tools(dt.id, dt.content)
                for mt in m_tools:
                    # Prefix MCP name with the tool name to avoid collisions?
                    available[mt.name] = mt
        except Exception as e:
            logger.error(f"Error loading tool {dt.name}: {e}")

    return available
