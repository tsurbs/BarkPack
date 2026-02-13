"""FlareSolverr tools for scraping Cloudflare-protected websites.

FlareSolverr is a proxy server that uses a headless browser to solve
Cloudflare challenges, returning the page HTML.  It complements the
Firecrawl scraping tools by handling sites that block automated access.

Requires a running FlareSolverr instance.  Configure the URL via the
FLARESOLVERR_URL environment variable (default: http://localhost:8191).
"""

import logging
import os

import httpx

from bark.core.tools import tool

logger = logging.getLogger(__name__)

_DEFAULT_FLARESOLVERR_URL = "http://localhost:8191"
_MAX_TIMEOUT = 60000  # ms – maximum time FlareSolverr will wait for a solve
_RESPONSE_TIMEOUT = 90  # seconds – httpx timeout (must exceed _MAX_TIMEOUT)
_MAX_HTML_LENGTH = 50000  # truncate very large pages to avoid token overflow


def _get_flaresolverr_url() -> str:
    """Return the FlareSolverr base URL from env or settings."""
    url = os.environ.get("FLARESOLVERR_URL", "")
    if not url:
        from bark.core.config import get_settings

        url = get_settings().flaresolverr_url
    return url or _DEFAULT_FLARESOLVERR_URL


@tool(
    name="flaresolverr_scrape",
    description=(
        "Scrape a webpage using FlareSolverr, which can bypass Cloudflare and "
        "similar bot-protection challenges.  Returns the raw HTML of the page.  "
        "Use this when firecrawl_scrape fails due to Cloudflare blocking."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to scrape (must be a full URL starting with http:// or https://)",
            },
        },
        "required": ["url"],
    },
)
async def flaresolverr_scrape(url: str) -> str:
    """Scrape a single URL via FlareSolverr."""
    base_url = _get_flaresolverr_url()

    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": _MAX_TIMEOUT,
    }

    try:
        async with httpx.AsyncClient(timeout=_RESPONSE_TIMEOUT) as client:
            resp = await client.post(f"{base_url}/v1", json=payload)
            resp.raise_for_status()
    except httpx.ConnectError:
        logger.error("FlareSolverr not reachable at %s", base_url)
        return (
            f"❌ Could not connect to FlareSolverr at `{base_url}`. "
            "Make sure FlareSolverr is running and FLARESOLVERR_URL is set correctly."
        )
    except httpx.TimeoutException:
        logger.error("FlareSolverr request timed out for %s", url)
        return (
            f"❌ FlareSolverr request timed out while scraping `{url}`. "
            "The page may be too slow to load or the challenge too complex."
        )
    except httpx.HTTPStatusError as e:
        logger.error("FlareSolverr HTTP error: %s", e)
        return f"❌ FlareSolverr returned HTTP {e.response.status_code}."

    data = resp.json()

    status = data.get("status")
    if status != "ok":
        message = data.get("message", "unknown error")
        logger.warning("FlareSolverr solve failed for %s: %s", url, message)
        return f"❌ FlareSolverr could not solve the page: {message}"

    solution = data.get("solution", {})
    html = solution.get("response", "")

    if not html:
        return f"❌ FlareSolverr returned an empty response for `{url}`."

    # Truncate very long pages
    if len(html) > _MAX_HTML_LENGTH:
        html = html[:_MAX_HTML_LENGTH] + "\n\n...(truncated)..."

    solved_url = solution.get("url", url)
    status_code = solution.get("status", "?")

    return (
        f"# FlareSolverr result for {url}\n"
        f"*Solved URL: {solved_url} — HTTP {status_code}*\n\n"
        f"```html\n{html}\n```"
    )


@tool(
    name="flaresolverr_status",
    description=(
        "Check whether FlareSolverr is running and healthy.  "
        "Returns version info if available.  Use this to verify "
        "the service is up before attempting to scrape."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def flaresolverr_status() -> str:
    """Check FlareSolverr health."""
    base_url = _get_flaresolverr_url()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/health")
            resp.raise_for_status()
    except httpx.ConnectError:
        return (
            f"❌ FlareSolverr is **not reachable** at `{base_url}`. "
            "Make sure the service is running and FLARESOLVERR_URL is set correctly."
        )
    except httpx.TimeoutException:
        return f"❌ FlareSolverr at `{base_url}` did not respond in time."
    except httpx.HTTPStatusError as e:
        # Some FlareSolverr versions don't have /health — fall back to /v1
        try:
            async with httpx.AsyncClient(timeout=10) as client2:
                probe = await client2.post(
                    f"{base_url}/v1",
                    json={"cmd": "sessions.list"},
                )
                probe.raise_for_status()
                probe_data = probe.json()
                version = probe_data.get("version", "unknown")
                return (
                    f"✅ FlareSolverr is **running** at `{base_url}`\n"
                    f"• Version: {version}\n"
                    f"• Note: /health returned HTTP {e.response.status_code} "
                    "but the API is responding."
                )
        except Exception:
            return f"❌ FlareSolverr at `{base_url}` returned HTTP {e.response.status_code}."

    # Successful /health response
    try:
        data = resp.json()
    except Exception:
        # /health may return plain text
        return f"✅ FlareSolverr is **running** at `{base_url}` (health check OK)."

    version = data.get("version", data.get("msg", "unknown"))
    return (
        f"✅ FlareSolverr is **running** at `{base_url}`\n"
        f"• Version: {version}"
    )
