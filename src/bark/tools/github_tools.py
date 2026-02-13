"""GitHub tools for reading files from public and private repositories."""

import base64
import logging
import re
from urllib.parse import unquote

import httpx

from bark.core.tools import tool

logger = logging.getLogger(__name__)

# GitHub blob URL pattern:
# https://github.com/{owner}/{repo}/blob/{ref}/{path...}
_GITHUB_BLOB_RE = re.compile(
    r"^https?://github\.com/"
    r"(?P<owner>[^/]+)/"
    r"(?P<repo>[^/]+)/"
    r"blob/"
    r"(?P<ref>[^/]+)/"
    r"(?P<path>.+)$"
)


async def _fetch_github_file(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
) -> str:
    """Fetch a file from GitHub via the Contents API.

    Returns a formatted string with the file content and metadata.
    Works for public repos without auth; honours a GITHUB_TOKEN env-var
    if one is set (for private repos or higher rate limits).
    """
    import os

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    params: dict[str, str] = {}
    if ref:
        params["ref"] = ref

    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Bark-Bot",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)

        # ── Error handling ──────────────────────────────────────────
        if resp.status_code == 404:
            return (
                f"❌ File not found: `{owner}/{repo}/{path}`"
                + (f" (ref: {ref})" if ref else "")
                + "\n\nCheck that the repository is public (or that GITHUB_TOKEN is set) "
                "and the path is correct."
            )
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            reset = resp.headers.get("X-RateLimit-Reset", "?")
            return (
                f"❌ GitHub API rate limit or access denied (HTTP 403).\n"
                f"Rate-limit remaining: {remaining}, resets at: {reset}\n"
                "Tip: set a GITHUB_TOKEN environment variable for higher limits / private repo access."
            )
        if resp.status_code >= 400:
            return f"❌ GitHub API error: HTTP {resp.status_code}\n{resp.text[:500]}"

        data = resp.json()

        # ── Directory listing (the API returns a list for dirs) ─────
        if isinstance(data, list):
            entries = [
                f"  {'📁' if e.get('type') == 'dir' else '📄'} {e['name']}"
                for e in data[:50]
            ]
            more = f"\n  …and {len(data) - 50} more" if len(data) > 50 else ""
            return (
                f"📂 **{owner}/{repo}/{path}** is a directory "
                f"({len(data)} items):\n"
                + "\n".join(entries)
                + more
            )

        file_type = data.get("type", "file")
        size = data.get("size", 0)
        encoding = data.get("encoding", "")
        download_url = data.get("download_url", "")
        html_url = data.get("html_url", "")
        sha = data.get("sha", "")[:12]

        # ── Binary / non-base64 files ──────────────────────────────
        if file_type == "submodule":
            return (
                f"📦 **{path}** is a Git submodule pointing to:\n"
                f"  {data.get('submodule_git_url', data.get('html_url', '?'))}"
            )

        if file_type == "symlink":
            target = data.get("target", "?")
            return f"🔗 **{path}** is a symlink → `{target}`"

        # Large files (>100 KB) often have no inline content; fall back
        # to download_url.
        content_b64 = data.get("content")

        if content_b64 and encoding == "base64":
            try:
                decoded = base64.b64decode(content_b64).decode("utf-8", errors="replace")
            except Exception as exc:
                return f"❌ Failed to decode file content: {exc}"
        elif download_url:
            # For large files or non-base64, fetch via download_url
            try:
                dl_resp = await client.get(
                    download_url,
                    headers={"User-Agent": "Bark-Bot"},
                    follow_redirects=True,
                )
                dl_resp.raise_for_status()

                # Check if this looks like a binary file
                content_type = dl_resp.headers.get("content-type", "")
                if "image" in content_type or "octet-stream" in content_type:
                    human_size = (
                        f"{size / 1_048_576:.1f} MB"
                        if size > 1_048_576
                        else f"{size / 1024:.1f} KB"
                    )
                    return (
                        f"🖼️ **{path}** is a binary file ({human_size}).\n"
                        f"Type: {content_type}\n"
                        f"Download: {download_url}\n"
                        f"View on GitHub: {html_url}"
                    )

                decoded = dl_resp.text
            except httpx.HTTPStatusError as exc:
                return f"❌ Failed to download large file: HTTP {exc.response.status_code}"
            except Exception as exc:
                return f"❌ Failed to download file: {exc}"
        else:
            human_size = (
                f"{size / 1_048_576:.1f} MB"
                if size > 1_048_576
                else f"{size / 1024:.1f} KB"
            )
            return (
                f"📎 **{path}** ({human_size}) — content not available via API.\n"
                f"View on GitHub: {html_url}"
            )

        # ── Truncate very large text files ─────────────────────────
        max_chars = 60_000
        truncated = ""
        if len(decoded) > max_chars:
            truncated = (
                f"\n\n…(truncated at {max_chars:,} chars; "
                f"total {len(decoded):,} chars)…"
            )
            decoded = decoded[:max_chars]

        human_size = (
            f"{size / 1_048_576:.1f} MB"
            if size > 1_048_576
            else f"{size / 1024:.1f} KB"
        )
        ref_display = f" @ `{ref}`" if ref else ""

        header = (
            f"📄 **{owner}/{repo}/{path}**{ref_display}  "
            f"({human_size}, sha `{sha}`)\n"
            f"View on GitHub: {html_url}\n\n"
            "---\n\n"
        )

        return header + decoded + truncated


# ── Tool 1: structured owner/repo/path ──────────────────────────────


@tool(
    name="github_read_file",
    description=(
        "Read a file from a GitHub repository. "
        "Fetches the raw file content using the GitHub API. "
        "Works with public repos by default; set the GITHUB_TOKEN env var for private repos.\n\n"
        "Returns the file content as text with metadata (size, SHA, URL). "
        "For binary files, returns metadata and a download link instead."
    ),
    parameters={
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner (user or org), e.g. 'scottylabs'",
            },
            "repo": {
                "type": "string",
                "description": "Repository name, e.g. 'wikinotes'",
            },
            "path": {
                "type": "string",
                "description": (
                    "Path to the file within the repo, e.g. 'CONTRIBUTING.md' or "
                    "'src/utils/helpers.py'. Can also be a directory to list its contents."
                ),
            },
            "ref": {
                "type": "string",
                "description": (
                    "Branch, tag, or commit SHA to read from (optional, defaults to "
                    "the repo's default branch). Examples: 'main', 'develop', 'v1.0.0'"
                ),
            },
        },
        "required": ["owner", "repo", "path"],
    },
)
async def github_read_file(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
) -> str:
    """Read a file from a GitHub repository by owner/repo/path."""
    return await _fetch_github_file(owner, repo, path, ref)


# ── Tool 2: full GitHub URL ─────────────────────────────────────────


@tool(
    name="github_read_url",
    description=(
        "Read a file from GitHub given its full URL. "
        "Accepts URLs like https://github.com/owner/repo/blob/branch/path/to/file.md "
        "and fetches the raw file content.\n\n"
        "Returns the file content as text with metadata (size, SHA, URL). "
        "For binary files, returns metadata and a download link instead."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": (
                    "Full GitHub file URL, e.g. "
                    "'https://github.com/scottylabs/wikinotes/blob/main/CONTRIBUTING.md'"
                ),
            },
        },
        "required": ["url"],
    },
)
async def github_read_url(url: str) -> str:
    """Read a file from GitHub by parsing a full GitHub blob URL."""
    url = url.strip()
    match = _GITHUB_BLOB_RE.match(url)
    if not match:
        return (
            "❌ Could not parse GitHub URL. Expected format:\n"
            "`https://github.com/{owner}/{repo}/blob/{branch}/{path}`\n\n"
            f"Got: `{url}`\n\n"
            "Tip: use `github_read_file` with explicit owner/repo/path parameters instead."
        )

    owner = unquote(match.group("owner"))
    repo = unquote(match.group("repo"))
    ref = unquote(match.group("ref"))
    path = unquote(match.group("path"))

    return await _fetch_github_file(owner, repo, path, ref)
