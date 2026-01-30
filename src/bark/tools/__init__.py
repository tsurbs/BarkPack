"""Context tools for wiki search and refresh."""

from bark.context.engine import get_context_engine
from bark.core.tools import tool


@tool(
    name="refresh_context",
    description="Refresh the wiki context from GitHub. Use this when the wiki may have been updated or when search returns no results.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def refresh_context() -> str:
    """Refresh the wiki context by re-cloning and re-ingesting the wiki."""
    engine = get_context_engine()
    return await engine.refresh()


@tool(
    name="search_notion",
    description="Search Notion pages for information. Searches page titles and content in real-time using the Notion API. Use this to find ScottyLabs Notion documents, meeting notes, project pages, etc.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant Notion pages",
            },
        },
        "required": ["query"],
    },
)
def search_notion(query: str) -> str:
    """Search Notion pages using the native API."""
    engine = get_context_engine()
    return engine.search_notion_live(query)


@tool(
    name="search_drive",
    description="Search Google Drive files for information. Searches file names and content in real-time using the Drive API. Use this to find ScottyLabs documents, spreadsheets, presentations, etc.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant Drive files",
            },
        },
        "required": ["query"],
    },
)
def search_drive(query: str) -> str:
    """Search Google Drive files using the native API."""
    engine = get_context_engine()
    return engine.search_drive_live(query)


@tool(
    name="search_wiki",
    description="Search the ScottyLabs wiki for information about processes, projects, policies, or anything ScottyLabs-related. Returns relevant sections from the wiki.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant wiki content",
            },
        },
        "required": ["query"],
    },
)
async def search_wiki(query: str) -> str:
    """Search the wiki for relevant content."""
    engine = get_context_engine()
    return await engine.search_formatted(query)


# Import memory tools to register them
from bark.tools.memory_tools import (  # noqa: F401, E402
    # New hierarchical memory tools
    memory_search,
    memory_grep,
    memory_list,
    memory_read,
    memory_write,
    memory_create_folder,
    memory_move,
    memory_delete,
    # Legacy tools (backwards compatibility)
    read_memory,
    write_memory,
    delete_memory,
    # Utility
    no_reply,
)


@tool(
    name="save_to_memory",
    description="""Save content from external sources (Drive, Notion, web) to memory.

Use this to save important information discovered during searches to the appropriate committee folder.
A summary will be extracted and stored as a memory file.

Example usage:
- After finding a budget doc in Drive: committee="finance", title="Q1 Budget 2025", content="...", source_url="..."
- After finding meeting notes: committee="admin", title="Board Meeting Jan 2025", content="..."
""",
    parameters={
        "type": "object",
        "properties": {
            "committee": {
                "type": "string",
                "description": "Committee folder (tech, labrador, design, events, outreach, finance, foundry, admin)",
            },
            "title": {
                "type": "string",
                "description": "Title for the memory (will be used as filename)",
            },
            "content": {
                "type": "string",
                "description": "Content to save (will be formatted with source info)",
            },
            "source_type": {
                "type": "string",
                "description": "Source type (drive, notion, wiki, web, other)",
            },
            "source_url": {
                "type": "string",
                "description": "Optional URL to the original source",
            },
        },
        "required": ["committee", "title", "content"],
    },
)
async def save_to_memory(
    committee: str,
    title: str,
    content: str,
    source_type: str = "other",
    source_url: str | None = None,
) -> str:
    """Save external content to memory with source attribution."""
    from bark.memory.memory_system import get_memory_system
    from bark.memory.memory_embeddings import get_memory_embeddings
    import logging
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    memory = get_memory_system()
    
    # Build memory content with metadata
    lines = [f"# {title}", ""]
    lines.append(f"*Saved: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    if source_type:
        lines.append(f"*Source: {source_type}*")
    if source_url:
        lines.append(f"*URL: {source_url}*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(content)
    
    full_content = "\n".join(lines)
    
    try:
        path = memory.write_file(committee, title, full_content)
        
        # Index for semantic search
        try:
            embeddings = get_memory_embeddings()
            embeddings.index_file(path, full_content)
        except Exception as e:
            logger.warning(f"Could not index saved content: {e}")
        
        return f"✅ Saved to memory: **{path}**"
    except (PermissionError, ValueError) as e:
        return f"❌ Error: {e}"

