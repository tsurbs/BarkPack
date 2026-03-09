"""
Tool for managing dynamic tools (Python and MCP) at runtime.
Allows the agent to create, update, delete, and list tools on the fly.
"""
import json
import logging
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.tools.base import BaseTool
from app.tools.registry import _compile_python_tool, build_mcp_tools
from app.db.models import DBTool
from app.models.user import User

logger = logging.getLogger(__name__)


class ManageToolArgs(BaseModel):
    """Arguments for the ManageTool action."""
    action: str = Field(
        description="The action to perform. One of: 'list', 'get', 'create', 'update', 'delete'."
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="The name of the tool to operate on. Required for 'get', 'update', and 'delete'."
    )
    tool_type: Optional[str] = Field(
        default=None,
        description="The type of tool: 'python' or 'mcp'. Required for 'create' and 'update'."
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of what the tool does. Required for 'create'."
    )
    content: Optional[str] = Field(
        default=None,
        description=(
            "The tool content. For 'python' tools, this is the Python code that defines "
            "an 'Args' class (pydantic BaseModel) and an async 'run(self, args, user, db)' function. "
            "For 'mcp' tools, this is a JSON object with 'command', 'args', and optional 'env' fields."
        )
    )


class ManageToolTool(BaseTool):
    """
    Manage dynamic tools stored in the database. Allows creating, reading,
    updating, and deleting Python and MCP tools at runtime.
    """
    name = "manage_tool"
    description = (
        "Manage dynamic tools available to the agent. Actions:\n"
        "- 'list': List all available tools with their types and descriptions.\n"
        "- 'get': Get full details of a specific tool including its code/config.\n"
        "- 'create': Create a new Python or MCP tool from code or config.\n"
        "- 'update': Update an existing tool's code or configuration.\n"
        "- 'delete': Remove a tool (cannot delete native tools)."
    )
    args_schema = ManageToolArgs

    async def run(self, args: ManageToolArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if db is None:
            return "Error: Database session required for tool management."

        action = args.action.lower()
        
        if action == "list":
            return await self._list_tools(db)
        elif action == "get":
            return await self._get_tool(args.tool_name, db)
        elif action == "create":
            return await self._create_tool(args.tool_name, args.tool_type, args.description, args.content, db)
        elif action == "update":
            return await self._update_tool(args.tool_name, args.tool_type, args.description, args.content, db)
        elif action == "delete":
            return await self._delete_tool(args.tool_name, db)
        else:
            return f"Error: Unknown action '{action}'. Valid actions: list, get, create, update, delete."

    async def _list_tools(self, db: AsyncSession) -> str:
        """List all available tools."""
        result = await db.execute(select(DBTool).order_by(DBTool.tool_type, DBTool.name))
        tools = result.scalars().all()

        if not tools:
            return "No tools found in the database."

        lines = ["Available Tools:\n"]
        
        # Group by type
        by_type = {}
        for t in tools:
            by_type.setdefault(t.tool_type, []).append(t)
        
        for tool_type in ["native", "python", "mcp"]:
            if tool_type in by_type:
                lines.append(f"**{tool_type.upper()} Tools:**")
                for t in by_type[tool_type]:
                    lines.append(f"  - `{t.name}`: {t.description[:80]}{'...' if len(t.description) > 80 else ''}")
                lines.append("")

        return "\n".join(lines)

    async def _get_tool(self, tool_name: Optional[str], db: AsyncSession) -> str:
        """Get details of a specific tool."""
        if not tool_name:
            return "Error: 'tool_name' is required for the 'get' action."

        result = await db.execute(select(DBTool).where(DBTool.name == tool_name))
        tool = result.scalars().first()

        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        lines = [
            f"**Tool:** `{tool.name}`",
            f"**Type:** {tool.tool_type}",
            f"**Description:** {tool.description}",
            f"**Created:** {tool.created_at.isoformat() if tool.created_at else 'N/A'}",
            f"**Updated:** {tool.updated_at.isoformat() if tool.updated_at else 'N/A'}",
            "",
            "**Content:**",
        ]

        if tool.tool_type == "python":
            lines.append(f"```python\n{tool.content}\n```")
        elif tool.tool_type == "mcp":
            lines.append(f"```json\n{tool.content}\n```")
        else:
            lines.append(f"```json\n{tool.content}\n```")

        return "\n".join(lines)

    async def _create_tool(
        self,
        tool_name: Optional[str],
        tool_type: Optional[str],
        description: Optional[str],
        content: Optional[str],
        db: AsyncSession
    ) -> str:
        """Create a new tool."""
        # Validation
        if not tool_name:
            return "Error: 'tool_name' is required for creating a tool."
        if not tool_type:
            return "Error: 'tool_type' is required for creating a tool. Must be 'python' or 'mcp'."
        if not description:
            return "Error: 'description' is required for creating a tool."
        if not content:
            return "Error: 'content' is required for creating a tool."

        tool_type = tool_type.lower()
        if tool_type not in ["python", "mcp"]:
            return f"Error: 'tool_type' must be 'python' or 'mcp', got '{tool_type}'."

        # Check if tool already exists
        result = await db.execute(select(DBTool).where(DBTool.name == tool_name))
        if result.scalars().first():
            return f"Error: Tool '{tool_name}' already exists. Use 'update' to modify it."

        # Validate the content
        if tool_type == "python":
            try:
                _compile_python_tool(tool_name, description, content)
            except Exception as e:
                return f"Error: Failed to compile Python tool: {e}"
        elif tool_type == "mcp":
            try:
                config = json.loads(content)
                if "command" not in config:
                    return "Error: MCP config must contain a 'command' field."
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON for MCP config: {e}"

        # Save to database
        new_tool = DBTool(
            name=tool_name,
            description=description,
            tool_type=tool_type,
            content=content
        )
        db.add(new_tool)
        await db.commit()

        logger.info(f"Created new {tool_type} tool: {tool_name}")
        return f"Successfully created {tool_type} tool '{tool_name}'. It will be available in the next tool refresh."

    async def _update_tool(
        self,
        tool_name: Optional[str],
        tool_type: Optional[str],
        description: Optional[str],
        content: Optional[str],
        db: AsyncSession
    ) -> str:
        """Update an existing tool."""
        if not tool_name:
            return "Error: 'tool_name' is required for updating a tool."

        result = await db.execute(select(DBTool).where(DBTool.name == tool_name))
        tool = result.scalars().first()

        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        if tool.tool_type == "native":
            return f"Error: Cannot update native tool '{tool_name}'. Native tools are read-only."

        # Update fields
        if description:
            tool.description = description
        if content:
            # Validate new content
            if tool.tool_type == "python" or tool_type == "python":
                try:
                    _compile_python_tool(tool_name, description or tool.description, content)
                except Exception as e:
                    return f"Error: Failed to compile Python tool: {e}"
            elif tool.tool_type == "mcp" or tool_type == "mcp":
                try:
                    config = json.loads(content)
                    if "command" not in config:
                        return "Error: MCP config must contain a 'command' field."
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON for MCP config: {e}"
            tool.content = content
        if tool_type and tool_type != tool.tool_type:
            return f"Error: Cannot change tool type from '{tool.tool_type}' to '{tool_type}'. Delete and recreate instead."

        await db.commit()
        logger.info(f"Updated tool: {tool_name}")
        return f"Successfully updated tool '{tool_name}'. Changes will take effect on next tool refresh."

    async def _delete_tool(self, tool_name: Optional[str], db: AsyncSession) -> str:
        """Delete a tool."""
        if not tool_name:
            return "Error: 'tool_name' is required for deleting a tool."

        result = await db.execute(select(DBTool).where(DBTool.name == tool_name))
        tool = result.scalars().first()

        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        if tool.tool_type == "native":
            return f"Error: Cannot delete native tool '{tool_name}'. Native tools are protected."

        await db.delete(tool)
        await db.commit()
        logger.info(f"Deleted tool: {tool_name}")
        return f"Successfully deleted tool '{tool_name}'."
