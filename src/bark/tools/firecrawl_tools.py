"""Firecrawl tool for scraping and crawling websites."""

import logging
import os

from bark.core.tools import tool

logger = logging.getLogger(__name__)


def _get_firecrawl():
    """Get a Firecrawl client instance."""
    from firecrawl import Firecrawl

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        from bark.core.config import get_settings
        api_key = get_settings().firecrawl_api_key

    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not set. Add it to your .env file.")

    return Firecrawl(api_key=api_key)


@tool(
    name="firecrawl_scrape",
    description=(
        "Scrape a single webpage and return its content as markdown. "
        "Great for reading articles, documentation, or any public web page."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to scrape",
            },
        },
        "required": ["url"],
    },
)
def firecrawl_scrape(url: str) -> str:
    """Scrape a single URL."""
    client = _get_firecrawl()
    result = client.scrape(url, formats=["markdown"])

    markdown = result.get("markdown", "")
    metadata = result.get("metadata", {})
    title = metadata.get("title", url)

    if not markdown:
        return f"No content extracted from {url}"

    # Truncate very long pages
    if len(markdown) > 15000:
        markdown = markdown[:15000] + "\n\n...(truncated)..."

    return f"# {title}\n*Source: {url}*\n\n{markdown}"


@tool(
    name="firecrawl_crawl",
    description=(
        "Crawl a website starting from a URL, following links up to a limit. "
        "Returns markdown content from multiple pages. Use for exploring an entire site."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The starting URL to crawl from",
            },
            "limit": {
                "type": "integer",
                "description": "Max pages to crawl (default 5, max 20)",
            },
        },
        "required": ["url"],
    },
)
def firecrawl_crawl(url: str, limit: int = 5) -> str:
    """Crawl a website."""
    limit = min(limit, 20)  # Cap at 20 to avoid excessive API usage
    client = _get_firecrawl()
    result = client.crawl(
        url,
        limit=limit,
        scrape_options={"formats": ["markdown"]},
    )

    pages = result.get("data", [])
    if not pages:
        return f"No pages crawled from {url}"

    output = [f"Crawled {len(pages)} page(s) from {url}:\n"]
    for i, page in enumerate(pages, 1):
        metadata = page.get("metadata", {})
        title = metadata.get("title", f"Page {i}")
        page_url = metadata.get("sourceURL", "?")
        markdown = page.get("markdown", "(no content)")

        # Truncate individual pages
        if len(markdown) > 5000:
            markdown = markdown[:5000] + "\n...(truncated)..."

        output.append(f"## {i}. {title}")
        output.append(f"*URL: {page_url}*\n")
        output.append(markdown)
        output.append("\n---\n")

    return "\n".join(output)


@tool(
    name="firecrawl_map",
    description=(
        "Map a website to discover all its pages/URLs without scraping content. "
        "Useful for understanding a site's structure before deciding what to scrape."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to map",
            },
        },
        "required": ["url"],
    },
)
def firecrawl_map(url: str) -> str:
    """Map a website's URLs."""
    client = _get_firecrawl()
    result = client.map(url)

    links = result.get("links", [])
    if not links:
        return f"No pages found on {url}"

    output = [f"Found {len(links)} page(s) on {url}:\n"]
    for link in links[:50]:  # Cap output
        output.append(f"- {link}")

    if len(links) > 50:
        output.append(f"\n...and {len(links) - 50} more")

    return "\n".join(output)
