"""Volume tools for downloading and managing files on the bark-volume.

The volume path is configurable via the BARK_VOLUME_PATH env var
(default: /bark-volume), making it compatible with Railway volumes.
"""

import io
import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from bark.core.tools import tool

logger = logging.getLogger(__name__)


def _default_volume_path() -> str:
    """Pick a writable default volume path.

    - If BARK_VOLUME_PATH is set, use it (Railway / explicit config).
    - If /bark-volume exists (Docker), use it.
    - Otherwise fall back to data/volume relative to the project root
      so it works locally without root permissions.
    """
    env_val = os.environ.get("BARK_VOLUME_PATH")
    if env_val:
        return env_val
    if Path("/bark-volume").exists():
        return "/bark-volume"
    # Local dev fallback — next to data/memory
    return os.path.join(os.getcwd(), "data", "volume")


VOLUME_PATH = _default_volume_path()


def _vol(subpath: str = "") -> Path:
    """Return a safe resolved path under the volume root.

    Raises ValueError if the resolved path escapes the volume root.
    """
    root = Path(VOLUME_PATH).resolve()
    target = (root / subpath).resolve() if subpath else root
    if not (target == root or str(target).startswith(str(root) + os.sep)):
        raise ValueError(f"Path escapes the volume root: {subpath}")
    return target


def _ensure_volume() -> Path:
    """Ensure the volume directory exists."""
    root = Path(VOLUME_PATH)
    root.mkdir(parents=True, exist_ok=True)
    return root


# =============================================================================
# DOWNLOAD TOOLS
# =============================================================================


@tool(
    name="volume_download",
    description=(
        "Download a file from a URL and save it to the bark-volume workspace. "
        "Returns the path on the volume where the file was saved."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to download",
            },
            "filename": {
                "type": "string",
                "description": (
                    "Filename to save as (optional, auto-detected from URL). "
                    "Can include subdirectories, e.g. 'data/report.csv'"
                ),
            },
        },
        "required": ["url"],
    },
)
async def volume_download(url: str, filename: str = "") -> str:
    """Download a file from a URL to the volume."""
    import httpx

    _ensure_volume()

    # Determine filename
    if not filename:
        parsed = urlparse(url)
        filename = unquote(Path(parsed.path).name) or "download"

    dest = _vol(filename)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        size = dest.stat().st_size
        human_size = (
            f"{size / 1_048_576:.1f} MB" if size > 1_048_576 else f"{size / 1024:.1f} KB"
        )
        return f"✅ Downloaded to `{dest}` ({human_size})"
    except httpx.HTTPStatusError as e:
        return f"❌ Download failed: HTTP {e.response.status_code} for {url}"
    except Exception as e:
        return f"❌ Download failed: {e}"


@tool(
    name="volume_download_drive",
    description=(
        "Download a file from Google Drive by its file ID and save it to the bark-volume. "
        "Works with Google Docs (exports as text), Sheets (exports as CSV), "
        "and regular uploaded files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The Google Drive file ID",
            },
            "filename": {
                "type": "string",
                "description": (
                    "Filename to save as (optional, auto-detected from Drive metadata). "
                    "Can include subdirectories."
                ),
            },
        },
        "required": ["file_id"],
    },
)
def volume_download_drive(file_id: str, filename: str = "") -> str:
    """Download a Google Drive file to the volume."""
    from googleapiclient.http import MediaIoBaseDownload

    from bark.context.google_auth import get_google_auth

    _ensure_volume()

    auth = get_google_auth()
    svc = auth.drive

    # Get metadata
    meta = svc.files().get(fileId=file_id, fields="name, mimeType").execute()
    name = meta.get("name", "untitled")
    mime = meta.get("mimeType", "")

    # Export map for Google-native types
    export_map = {
        "application/vnd.google-apps.document": ("text/plain", ".txt"),
        "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
        "application/vnd.google-apps.presentation": ("text/plain", ".txt"),
    }

    if mime in export_map:
        export_mime, ext = export_map[mime]
        content = svc.files().export(fileId=file_id, mimeType=export_mime).execute()
        if isinstance(content, bytes):
            pass  # already bytes
        else:
            content = content.encode("utf-8")

        if not filename:
            filename = Path(name).stem + ext
        dest = _vol(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    else:
        # Regular file — stream download
        if not filename:
            filename = name

        dest = _vol(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)

        request = svc.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest.write_bytes(buffer.getvalue())

    size = dest.stat().st_size
    human_size = (
        f"{size / 1_048_576:.1f} MB" if size > 1_048_576 else f"{size / 1024:.1f} KB"
    )
    return f"✅ Downloaded `{name}` to `{dest}` ({human_size})"


# =============================================================================
# VOLUME MANAGEMENT TOOLS
# =============================================================================


@tool(
    name="volume_list",
    description="List files and directories in the bark-volume workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Subdirectory to list (optional, defaults to volume root)",
            },
        },
    },
)
def volume_list(path: str = "") -> str:
    """List files in the volume."""
    _ensure_volume()
    target = _vol(path)

    if not target.exists():
        return f"❌ Path not found: {path}"
    if not target.is_dir():
        return f"❌ Not a directory: {path}"

    entries = sorted(target.iterdir())
    if not entries:
        return f"Volume directory `{target}` is empty."

    lines = [f"Contents of `{target}` ({len(entries)} items):"]
    for e in entries:
        if e.is_dir():
            count = sum(1 for _ in e.rglob("*") if _.is_file())
            lines.append(f"  📁 {e.name}/ ({count} files)")
        else:
            sz = e.stat().st_size
            human = f"{sz / 1_048_576:.1f}MB" if sz > 1_048_576 else f"{sz / 1024:.1f}KB"
            lines.append(f"  📄 {e.name} ({human})")
    return "\n".join(lines)


@tool(
    name="volume_read",
    description=(
        "Read the text contents of a file from the bark-volume. "
        "Returns the first 50,000 characters. Use for text files (csv, txt, json, py, etc.)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file within the volume",
            },
            "max_chars": {
                "type": "integer",
                "description": "Max characters to return (default 50000)",
            },
        },
        "required": ["path"],
    },
)
def volume_read(path: str, max_chars: int = 50000) -> str:
    """Read a text file from the volume."""
    target = _vol(path)

    if not target.exists():
        return f"❌ File not found: {path}"
    if target.is_dir():
        return f"❌ Path is a directory, not a file: {path}"

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"❌ Error reading file: {e}"

    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n...(truncated at {max_chars} chars, total {len(text)})..."
    return text


@tool(
    name="volume_delete",
    description="Delete a file or empty directory from the bark-volume workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or empty directory to delete",
            },
        },
        "required": ["path"],
    },
)
def volume_delete(path: str) -> str:
    """Delete a file from the volume."""
    target = _vol(path)

    if not target.exists():
        return f"❌ File not found: {path}"

    try:
        if target.is_dir():
            target.rmdir()  # Only removes empty dirs for safety
        else:
            target.unlink()
        return f"✅ Deleted `{target}`"
    except OSError as e:
        return f"❌ Error deleting: {e}"
