"""Core memory system for hierarchical filesystem-based memory storage."""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Committee folders - memories are organized by committee
COMMITTEES = [
    "tech",
    "labrador", 
    "design",
    "events",
    "outreach",
    "finance",
    "foundry",
    "admin",
]

# Memory storage path - persists in container volume or locally
MEMORY_DIR = Path("/app/data/memory") if Path("/app").exists() else Path("./data/memory")
CORE_FILE = "core.md"


class MemorySystem:
    """Manages the hierarchical memory filesystem."""

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize the memory system.
        
        Args:
            base_dir: Optional base directory override for testing
        """
        # Always resolve to absolute path to ensure consistent path operations
        self.base_dir = (base_dir or MEMORY_DIR).resolve()
        self._initialized = False

    def initialize(self) -> None:
        """Create the memory folder structure if it doesn't exist."""
        if self._initialized:
            return
            
        # Create base directory
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create committee folders
        for committee in COMMITTEES:
            (self.base_dir / committee).mkdir(exist_ok=True)
        
        # Create core.md if it doesn't exist
        core_path = self.base_dir / CORE_FILE
        if not core_path.exists():
            core_path.write_text(self._get_default_core_content())
            logger.info("Created core.md with default content")
        
        self._initialized = True
        logger.info(f"Memory system initialized at {self.base_dir}")

    def _get_default_core_content(self) -> str:
        """Get the default core.md content."""
        return """# Bark Core Context

## About Bark
Bark is the ScottyLabs AI assistant, designed to help team members with organizational knowledge, project management, and committee coordination.

## Creator & Leadership
- **Creator**: Theo Urban
- **Role**: 2025-26 Director of ScottyLabs

## Core Functionality
Bark provides:
- Knowledge retrieval from Notion, Google Drive, and GitHub Wiki
- Persistent memory across conversations
- Committee-specific context awareness
- Tool-based interactions for common tasks

## ScottyLabs Committees
- **Tech**: Engineering and development
- **Labrador**: TartanHacks organization
- **Design**: Visual design and branding
- **Events**: Event planning and logistics
- **Outreach**: Marketing and communications
- **Finance**: Budget and sponsorships
- **Foundry**: Project incubation
- **Admin**: Operations and leadership
"""

    def is_protected(self, path: str | Path) -> bool:
        """Check if a path is the protected core.md file.
        
        Args:
            path: Path to check (relative or absolute)
            
        Returns:
            True if the path refers to core.md
        """
        path = Path(path)
        # Check if it's core.md directly or points to base_dir/core.md
        if path.name == CORE_FILE:
            if path.is_absolute():
                return path == self.base_dir / CORE_FILE
            return str(path) == CORE_FILE or path == Path(CORE_FILE)
        return False

    def _validate_path(self, path: str | Path) -> Path:
        """Validate and resolve a memory path.
        
        Args:
            path: Relative path within memory system
            
        Returns:
            Resolved absolute path
            
        Raises:
            ValueError: If path escapes memory directory
        """
        self.initialize()
        
        resolved = (self.base_dir / path).resolve()
        
        # Ensure path stays within memory directory
        try:
            resolved.relative_to(self.base_dir.resolve())
        except ValueError:
            raise ValueError(f"Path '{path}' escapes memory directory")
        
        return resolved

    def _validate_committee(self, committee: str) -> None:
        """Validate committee name.
        
        Args:
            committee: Committee name to validate
            
        Raises:
            ValueError: If committee is not valid
        """
        if committee not in COMMITTEES:
            raise ValueError(
                f"Invalid committee '{committee}'. Valid committees: {', '.join(COMMITTEES)}"
            )

    def list_folder(self, folder_path: str = "") -> list[dict[str, Any]]:
        """List files and subfolders in a memory folder.
        
        Args:
            folder_path: Relative path within memory directory (empty for root)
            
        Returns:
            List of items with name, type, and size info
        """
        path = self._validate_path(folder_path)
        
        if not path.exists():
            return []
        
        if not path.is_dir():
            raise ValueError(f"Path '{folder_path}' is not a directory")
        
        items = []
        for item in sorted(path.iterdir()):
            # Skip hidden files and legacy memory.json
            if item.name.startswith(".") or item.name == "memory.json":
                continue
                
            item_info = {
                "name": item.name,
                "path": str(item.relative_to(self.base_dir)),
                "type": "folder" if item.is_dir() else "file",
            }
            
            if item.is_file():
                item_info["size"] = item.stat().st_size
                item_info["protected"] = self.is_protected(item)
            elif item.is_dir():
                # Count children
                item_info["children"] = len(list(item.iterdir()))
            
            items.append(item_info)
        
        return items

    def read_file(self, file_path: str) -> str:
        """Read a memory file's content.
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            File content as string
        """
        path = self._validate_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Memory file '{file_path}' not found")
        
        if path.is_dir():
            raise ValueError(f"Path '{file_path}' is a directory, not a file")
        
        return path.read_text(encoding="utf-8")

    def write_file(
        self,
        committee: str,
        filename: str,
        content: str,
        subfolder: str | None = None,
    ) -> str:
        """Write or update a memory file in a committee folder.
        
        Args:
            committee: Committee folder name
            filename: Name for the memory file (will add .md if not present)
            content: Content to write
            subfolder: Optional subfolder within committee
            
        Returns:
            Path to the created file (relative to memory dir)
        """
        self._validate_committee(committee)
        
        # Ensure .md extension
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        
        # Sanitize filename
        filename = self._sanitize_filename(filename)
        
        # Build path
        if subfolder:
            folder_path = self.base_dir / committee / subfolder
            folder_path.mkdir(parents=True, exist_ok=True)
            file_path = folder_path / filename
        else:
            file_path = self.base_dir / committee / filename
        
        # Check if trying to write to core.md
        if self.is_protected(file_path):
            raise PermissionError("Cannot modify core.md - this file is protected")
        
        file_path.write_text(content, encoding="utf-8")
        
        relative_path = str(file_path.relative_to(self.base_dir))
        logger.info(f"Wrote memory file: {relative_path}")
        
        return relative_path

    def create_folder(self, committee: str, folder_name: str) -> str:
        """Create a subfolder within a committee folder.
        
        Args:
            committee: Committee folder name
            folder_name: Name for the new folder
            
        Returns:
            Path to the created folder (relative to memory dir)
        """
        self._validate_committee(committee)
        
        folder_name = self._sanitize_filename(folder_name)
        folder_path = self.base_dir / committee / folder_name
        
        folder_path.mkdir(parents=True, exist_ok=True)
        
        relative_path = str(folder_path.relative_to(self.base_dir))
        logger.info(f"Created folder: {relative_path}")
        
        return relative_path

    def delete_file(self, file_path: str) -> bool:
        """Delete a memory file.
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            True if deleted successfully
        """
        path = self._validate_path(file_path)
        
        if self.is_protected(file_path):
            raise PermissionError("Cannot delete core.md - this file is protected")
        
        if not path.exists():
            return False
        
        if path.is_dir():
            # Only delete empty directories
            if any(path.iterdir()):
                raise ValueError(f"Cannot delete non-empty folder '{file_path}'")
            path.rmdir()
        else:
            path.unlink()
        
        logger.info(f"Deleted: {file_path}")
        return True

    def move_file(self, src_path: str, dst_path: str) -> str:
        """Move/reorganize a memory file.
        
        Args:
            src_path: Source path (relative to memory dir)
            dst_path: Destination path (relative to memory dir)
            
        Returns:
            New path of the file
        """
        src = self._validate_path(src_path)
        dst = self._validate_path(dst_path)
        
        if self.is_protected(src_path):
            raise PermissionError("Cannot move core.md - this file is protected")
        
        if not src.exists():
            raise FileNotFoundError(f"Source path '{src_path}' not found")
        
        # If dst is a directory, move into it
        if dst.is_dir():
            dst = dst / src.name
        
        # Ensure parent exists
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        src.rename(dst)
        
        relative_path = str(dst.relative_to(self.base_dir))
        logger.info(f"Moved {src_path} -> {relative_path}")
        
        return relative_path

    def text_search(
        self,
        query: str,
        folder: str | None = None,
        case_sensitive: bool = False,
    ) -> list[dict[str, Any]]:
        """Search memory files using plain text matching.
        
        Args:
            query: Text to search for
            folder: Optional folder to limit search (committee name or subfolder path)
            case_sensitive: Whether search should be case-sensitive
            
        Returns:
            List of matches with file path and matching lines
        """
        self.initialize()
        
        if folder:
            search_path = self._validate_path(folder)
            if not search_path.is_dir():
                raise ValueError(f"Search path '{folder}' is not a directory")
        else:
            search_path = self.base_dir
        
        results = []
        pattern = query if case_sensitive else query.lower()
        
        for md_file in search_path.rglob("*.md"):
            # Skip hidden files
            if any(part.startswith(".") for part in md_file.parts):
                continue
            
            try:
                content = md_file.read_text(encoding="utf-8")
                search_content = content if case_sensitive else content.lower()
                
                if pattern in search_content:
                    # Find matching lines
                    matches = []
                    for i, line in enumerate(content.split("\n"), 1):
                        search_line = line if case_sensitive else line.lower()
                        if pattern in search_line:
                            matches.append({
                                "line_number": i,
                                "content": line.strip()[:200],  # Truncate long lines
                            })
                    
                    results.append({
                        "path": str(md_file.relative_to(self.base_dir)),
                        "protected": self.is_protected(md_file),
                        "matches": matches[:10],  # Limit matches per file
                    })
            except Exception as e:
                logger.warning(f"Error searching {md_file}: {e}")
        
        return results

    def get_core_content(self) -> str:
        """Get the content of core.md.
        
        Returns:
            Core.md content
        """
        self.initialize()
        return self.read_file(CORE_FILE)

    def get_all_memories_summary(self) -> str:
        """Get a summary of all memories for system prompt injection.
        
        Returns:
            Formatted summary of memory contents
        """
        self.initialize()
        
        lines = ["**Memory System Contents:**", ""]
        
        # Add core.md
        lines.append(f"📋 **core.md** (protected)")
        
        # Add committee folders
        for committee in COMMITTEES:
            folder_path = self.base_dir / committee
            if folder_path.exists():
                items = list(folder_path.rglob("*.md"))
                count = len(items)
                if count > 0:
                    lines.append(f"📁 **{committee}/**: {count} file(s)")
                    for item in items[:5]:  # Show first 5
                        rel_path = item.relative_to(folder_path)
                        lines.append(f"   - {rel_path}")
                    if count > 5:
                        lines.append(f"   - ... and {count - 5} more")
                else:
                    lines.append(f"📁 **{committee}/**: (empty)")
        
        return "\n".join(lines)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a filename to be safe for filesystem.
        
        Args:
            name: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace unsafe characters
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(". ")
        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized)
        return sanitized or "unnamed"


# Global instance
_memory_system: MemorySystem | None = None


def get_memory_system() -> MemorySystem:
    """Get the global memory system instance."""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
        _memory_system.initialize()
    return _memory_system
