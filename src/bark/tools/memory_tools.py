"""Memory tools for persistent storage across conversations.

This module provides two sets of memory tools:
1. New hierarchical filesystem-based tools (memory_search, memory_grep, memory_list, etc.)
2. Legacy key-value tools (read_memory, write_memory, delete_memory) for backwards compatibility
"""

import json
import logging
from pathlib import Path

from bark.core.tools import tool

logger = logging.getLogger(__name__)

# Legacy memory storage path
MEMORY_DIR = Path("/app/data/memory") if Path("/app").exists() else Path("./data/memory")


# =============================================================================
# NEW HIERARCHICAL MEMORY TOOLS
# =============================================================================


@tool(
    name="memory_search",
    description="""Search memory files using semantic search (meaning-based). Finds memories related to your query even if they don't contain exact words.

Use this tool to find memories about a topic across all committees or within a specific folder. Returns ranked results by relevance.

Example queries:
- "meeting notes about sponsorships" 
- "design guidelines for TartanHacks"
- "tech committee decisions about infrastructure"
""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Semantic search query describing what you're looking for",
            },
            "folder": {
                "type": "string",
                "description": "Optional committee folder to limit search (e.g., 'tech', 'events', 'finance'). Leave empty to search all memories.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
            },
        },
        "required": ["query"],
    },
)
async def memory_search(query: str, folder: str | None = None, limit: int = 5) -> str:
    """Search memories using semantic similarity."""
    from bark.memory.memory_embeddings import get_memory_embeddings
    
    embeddings = get_memory_embeddings()
    results = embeddings.semantic_search(query, folder=folder, k=limit)
    
    if not results:
        if folder:
            return f"No memories found matching '{query}' in folder '{folder}'."
        return f"No memories found matching '{query}'."
    
    lines = [f"**Found {len(results)} memories matching '{query}':**\n"]
    for r in results:
        protected = " 🔒" if r.get("protected") else ""
        lines.append(f"### {r['path']}{protected} (relevance: {r['score']})")
        lines.append(f"{r['preview']}\n")
    
    return "\n".join(lines)


@tool(
    name="memory_grep",
    description="""Search memory files using plain text search (exact matching). Finds memories containing the exact text you specify.

Use this when you know specific words or phrases that should appear in the memory.

Example searches:
- "budget 2025" - finds files containing exactly "budget 2025"
- "Theo" - finds files mentioning Theo
""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text to search for in memory files",
            },
            "folder": {
                "type": "string",
                "description": "Optional folder path to limit search (e.g., 'tech', 'events/tartanhacks')",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether search should be case-sensitive (default: false)",
            },
        },
        "required": ["query"],
    },
)
async def memory_grep(query: str, folder: str | None = None, case_sensitive: bool = False) -> str:
    """Search memories using plain text matching."""
    from bark.memory.memory_system import get_memory_system
    
    memory = get_memory_system()
    results = memory.text_search(query, folder=folder, case_sensitive=case_sensitive)
    
    if not results:
        if folder:
            return f"No memories containing '{query}' found in folder '{folder}'."
        return f"No memories containing '{query}' found."
    
    lines = [f"**Found {len(results)} files containing '{query}':**\n"]
    for r in results:
        protected = " 🔒" if r.get("protected") else ""
        lines.append(f"### {r['path']}{protected}")
        for match in r["matches"][:3]:  # Show first 3 matches
            lines.append(f"  Line {match['line_number']}: {match['content']}")
        lines.append("")
    
    return "\n".join(lines)


@tool(
    name="memory_list",
    description="""List files and subfolders in a memory folder.

Use this to browse the memory structure and see what files exist.

Valid top-level folders (committees): tech, labrador, design, events, outreach, finance, foundry, admin

Examples:
- "" (empty) - lists all top-level items including core.md and committee folders
- "tech" - lists files in the tech committee folder
- "events/tartanhacks" - lists files in a subfolder
""",
    parameters={
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Folder path to list. Leave empty for root directory.",
            },
        },
        "required": [],
    },
)
async def memory_list(folder: str = "") -> str:
    """List contents of a memory folder."""
    from bark.memory.memory_system import get_memory_system
    
    memory = get_memory_system()
    
    try:
        items = memory.list_folder(folder)
    except ValueError as e:
        return f"Error: {e.with_traceback()}"
    
    if not items:
        if folder:
            return f"Folder '{folder}' is empty."
        return "Memory system is empty."
    
    lines = [f"**Contents of {'/' + folder if folder else 'memory root'}:**\n"]
    
    for item in items:
        if item["type"] == "folder":
            child_count = item.get("children", 0)
            lines.append(f"📁 **{item['name']}/** ({child_count} items)")
        else:
            protected = " 🔒" if item.get("protected") else ""
            size = item.get("size", 0)
            lines.append(f"📄 {item['name']}{protected} ({size} bytes)")
    
    return "\n".join(lines)


@tool(
    name="memory_read",
    description="""Read the contents of a memory file.

Use this to view the full content of a specific memory file.

Examples:
- "core.md" - read the core context (protected, read-only)
- "tech/infrastructure_decisions.md" - read a tech committee memory
""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the memory file (e.g., 'tech/meeting_notes.md')",
            },
        },
        "required": ["path"],
    },
)
async def memory_read(path: str) -> str:
    """Read a memory file's content."""
    from bark.memory.memory_system import get_memory_system
    
    memory = get_memory_system()
    
    try:
        content = memory.read_file(path)
        protected = " (🔒 protected - read-only)" if memory.is_protected(path) else ""
        return f"**{path}**{protected}\n\n{content}"
    except FileNotFoundError:
        return f"Memory file '{path}' not found."
    except ValueError as e:
        return f"Error: {e.with_traceback()}"


@tool(
    name="memory_write",
    description="""Create or update a memory file in a committee folder.

Use this to save important information that should be remembered across conversations.
Files are automatically saved with .md extension.

The core.md file is protected and cannot be modified.

Valid committees: tech, labrador, design, events, outreach, finance, foundry, admin

Examples:
- committee="tech", filename="api_decisions", content="..." - creates tech/api_decisions.md
- committee="events", filename="tartanhacks_2025", subfolder="tartanhacks" - creates events/tartanhacks/tartanhacks_2025.md
""",
    parameters={
        "type": "object",
        "properties": {
            "committee": {
                "type": "string",
                "description": "Committee folder (tech, labrador, design, events, outreach, finance, foundry, admin)",
            },
            "filename": {
                "type": "string",
                "description": "Name for the memory file (will add .md if needed)",
            },
            "content": {
                "type": "string",
                "description": "Content to save in the memory file (markdown format recommended)",
            },
            "subfolder": {
                "type": "string",
                "description": "Optional subfolder within the committee folder",
            },
        },
        "required": ["committee", "filename", "content"],
    },
)
async def memory_write(
    committee: str,
    filename: str, 
    content: str,
    subfolder: str | None = None,
) -> str:
    """Write a memory file to a committee folder."""
    from bark.memory.memory_system import get_memory_system
    from bark.memory.memory_embeddings import get_memory_embeddings
    
    memory = get_memory_system()
    
    try:
        path = memory.write_file(committee, filename, content, subfolder=subfolder)
        
        # Index the new file for semantic search
        try:
            embeddings = get_memory_embeddings()
            embeddings.index_file(path, content)
        except Exception as e:
            logger.warning(f"Could not index memory file: {e}")
        
        return f"✅ Saved memory to **{path}**"
    except PermissionError as e:
        return f"❌ {e}"
    except ValueError as e:
        return f"❌ Error: {e}"


@tool(
    name="memory_create_folder",
    description="""Create a subfolder within a committee folder.

Use this to organize memories into subfolders for better structure.

Examples:
- committee="events", folder_name="tartanhacks" - creates events/tartanhacks/
- committee="tech", folder_name="infrastructure" - creates tech/infrastructure/
""",
    parameters={
        "type": "object",
        "properties": {
            "committee": {
                "type": "string",
                "description": "Committee folder (tech, labrador, design, events, outreach, finance, foundry, admin)",
            },
            "folder_name": {
                "type": "string",
                "description": "Name for the new subfolder",
            },
        },
        "required": ["committee", "folder_name"],
    },
)
async def memory_create_folder(committee: str, folder_name: str) -> str:
    """Create a subfolder in a committee folder."""
    from bark.memory.memory_system import get_memory_system
    
    memory = get_memory_system()
    
    try:
        path = memory.create_folder(committee, folder_name)
        return f"✅ Created folder **{path}/**"
    except ValueError as e:
        return f"❌ Error: {e}"


@tool(
    name="memory_move",
    description="""Move or reorganize a memory file to a different location.

Use this to reorganize memories between folders.
The core.md file is protected and cannot be moved.

Examples:
- src="tech/notes.md", dst="tech/archive/notes.md" - move to archive subfolder
- src="events/meeting.md", dst="admin/" - move to admin folder
""",
    parameters={
        "type": "object",
        "properties": {
            "src": {
                "type": "string",
                "description": "Source path of the file to move",
            },
            "dst": {
                "type": "string",
                "description": "Destination path (folder or full path)",
            },
        },
        "required": ["src", "dst"],
    },
)
async def memory_move(src: str, dst: str) -> str:
    """Move a memory file to a new location."""
    from bark.memory.memory_system import get_memory_system
    from bark.memory.memory_embeddings import get_memory_embeddings
    
    memory = get_memory_system()
    
    try:
        new_path = memory.move_file(src, dst)
        
        # Update index
        try:
            embeddings = get_memory_embeddings()
            embeddings.remove_file(src)
            content = memory.read_file(new_path)
            embeddings.index_file(new_path, content)
        except Exception as e:
            logger.warning(f"Could not update index after move: {e}")
        
        return f"✅ Moved **{src}** → **{new_path}**"
    except PermissionError as e:
        return f"❌ {e}"
    except (FileNotFoundError, ValueError) as e:
        return f"❌ Error: {e}"


@tool(
    name="memory_delete",
    description="""Delete a memory file.

Use this to remove memories that are no longer needed.
The core.md file is protected and cannot be deleted.
Empty folders can also be deleted.

Examples:
- "tech/old_notes.md" - delete a file
- "events/archived/" - delete an empty folder
""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or empty folder to delete",
            },
        },
        "required": ["path"],
    },
)
async def memory_delete(path: str) -> str:
    """Delete a memory file."""
    from bark.memory.memory_system import get_memory_system
    from bark.memory.memory_embeddings import get_memory_embeddings
    
    memory = get_memory_system()
    
    try:
        deleted = memory.delete_file(path)
        if deleted:
            # Remove from index
            try:
                embeddings = get_memory_embeddings()
                embeddings.remove_file(path)
            except Exception as e:
                logger.warning(f"Could not remove from index: {e}")
            return f"✅ Deleted **{path}**"
        return f"File '{path}' not found."
    except PermissionError as e:
        return f"❌ {e}"
    except ValueError as e:
        return f"❌ Error: {e}"


# =============================================================================
# LEGACY KEY-VALUE MEMORY TOOLS (kept for backwards compatibility)
# =============================================================================


def _ensure_memory_dir() -> None:
    """Ensure memory directory exists."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _get_memory_file() -> Path:
    """Get the memory file path."""
    _ensure_memory_dir()
    return MEMORY_DIR / "memory.json"


def _load_memory() -> dict[str, str]:
    """Load all memories from storage."""
    memory_file = _get_memory_file()
    if memory_file.exists():
        try:
            return json.loads(memory_file.read_text())
        except json.JSONDecodeError:
            logger.warning("Memory file corrupted, starting fresh")
            return {}
    return {}


def _save_memory(memory: dict[str, str]) -> None:
    """Save memories to storage."""
    memory_file = _get_memory_file()
    memory_file.write_text(json.dumps(memory, indent=2))


@tool(
    name="read_memory",
    description="[Legacy] Read a stored memory by key. Use memory_search or memory_read for the new system.",
    parameters={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key/name of the memory to read. Use 'all' to list all memories.",
            },
        },
        "required": ["key"],
    },
)
async def read_memory(key: str) -> str:
    """Read a memory by key."""
    memory = _load_memory()

    if key == "all":
        if not memory:
            return "No legacy memories stored. Try memory_list() for the new system."
        entries = [f"- **{k}**: {v}" for k, v in memory.items()]
        return f"Legacy memories:\n" + "\n".join(entries)

    value = memory.get(key)
    if value:
        return f"Memory '{key}': {value}"
    return f"No memory found with key '{key}'."


@tool(
    name="write_memory",
    description="[Legacy] Save a key-value memory. Use memory_write for the new hierarchical system.",
    parameters={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "A short, descriptive key/name for the memory",
            },
            "value": {
                "type": "string",
                "description": "The information to remember",
            },
        },
        "required": ["key", "value"],
    },
)
async def write_memory(key: str, value: str) -> str:
    """Write a memory."""
    memory = _load_memory()
    is_update = key in memory
    memory[key] = value
    _save_memory(memory)

    if is_update:
        return f"Updated legacy memory '{key}'."
    return f"Saved new legacy memory '{key}'."


@tool(
    name="delete_memory",
    description="[Legacy] Delete a key-value memory. Use memory_delete for the new hierarchical system.",
    parameters={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key of the memory to delete",
            },
        },
        "required": ["key"],
    },
)
async def delete_memory(key: str) -> str:
    """Delete a memory."""
    memory = _load_memory()

    if key in memory:
        del memory[key]
        _save_memory(memory)
        return f"Deleted legacy memory '{key}'."
    return f"No legacy memory found with key '{key}'."


# =============================================================================
# UTILITY TOOLS
# =============================================================================


@tool(
    name="no_reply",
    description="Use this when you determine that no response is needed. For example, when a message wasn't directed at you, when someone is just chatting with others, or when your input wouldn't add value to the conversation.",
    parameters={
        "type": "object",
    },
)
async def no_reply() -> str:
    """Signal that no reply is needed."""
    return "__NO_REPLY__"
