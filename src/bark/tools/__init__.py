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

# Import Google Workspace tools to register them
from bark.tools.google_workspace_tools import (  # noqa: F401, E402
    # Gmail
    gmail_search,
    gmail_read,
    gmail_send,
    gmail_list_labels,
    # Calendar
    calendar_list_events,
    calendar_create_event,
    calendar_list_calendars,
    # Docs
    docs_get,
    docs_create,
    # Drive (enhanced)
    drive_list_files,
    drive_create_folder,
    drive_get_file_content,
    # Drive Activity
    drive_activity_query,
    # Drive Labels
    drive_labels_list,
    # Sheets
    sheets_read,
    sheets_write,
    # Forms
    forms_get,
    forms_list_responses,
    # Chat
    chat_list_spaces,
    chat_send_message,
    # Meet
    meet_create_space,
    meet_list_conference_records,
    # Admin SDK
    admin_list_users,
    admin_list_groups,
    # Apps Script
    apps_script_list_projects,
    apps_script_get_content,
    # Postmaster
    postmaster_list_domains,
    postmaster_get_traffic_stats,
    # Keep (stub)
    keep_note,
)

# Import Firecrawl tools to register them
from bark.tools.firecrawl_tools import (  # noqa: F401, E402
    firecrawl_scrape,
    firecrawl_crawl,
    firecrawl_map,
)

# Import FlareSolverr tools to register them
from bark.tools.flaresolverr_tools import (  # noqa: F401, E402
    flaresolverr_scrape,
    flaresolverr_status,
)

# Import document/spreadsheet tools to register them
from bark.tools.document_tools import (  # noqa: F401, E402
    # Spreadsheet metadata
    sheets_get_metadata,
    # Paginated reading
    sheets_read_chunk,
    # Search & filter
    sheets_search,
    sheets_filter_column,
    # Column statistics
    sheets_column_stats,
    # Append
    sheets_append,
    # Create
    sheets_create,
    # Tab management
    sheets_add_sheet,
    # Clear
    sheets_clear,
    # Export
    sheets_export_csv,
    # Batch row access
    sheets_get_rows,
    # Large doc reading
    docs_read_chunk,
)

# Import volume tools to register them
from bark.tools.volume_tools import (  # noqa: F401, E402
    volume_download,
    volume_download_drive,
    volume_list,
    volume_read,
    volume_delete,
)

# Import data processing tools to register them
from bark.tools.code_tools import (  # noqa: F401, E402
    data_agent,
)

# Import fullstack agent tools to register them
from bark.tools.frontend_tools import (  # noqa: F401, E402
    fullstack_agent,
)

# Import specialist delegation tools to register them
from bark.tools.specialist_tools import (  # noqa: F401, E402
    writing_agent,
    knowledge_agent,
)

# Import Claude Code integration tools
from bark.tools.claude_code_tools import (  # noqa: F401, E402
    code_edit_agent,
)

# Import weather tools to register them
from bark.tools.weather_tools import (  # noqa: F401, E402
    get_weather,
)

# Import agent team tools
from bark.tools.agent_team import (  # noqa: F401, E402
    research_agent,
    planner_agent,
    review_agent,
    comms_agent,
    analytics_agent,
    design_agent,
    security_agent,
    docs_agent,
    debug_agent,
    onboarding_agent,
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

