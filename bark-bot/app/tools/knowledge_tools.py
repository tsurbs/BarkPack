import os
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

from notion_client import AsyncClient
from tavily import AsyncTavilyClient
import httpx

class NotionSearchArgs(BaseModel):
    query: str = Field(description="The search string to find in Notion workspace.")

class SearchNotionTool(BaseTool):
    name = "search_notion"
    description = "Search across all Notion pages in the workspace for the given query."
    args_schema = NotionSearchArgs
    
    async def run(self, args: NotionSearchArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("NOTION_API_KEY")
        if not api_key or api_key == "your_notion_api_key_here":
            return "Error: NOTION_API_KEY is not set."
            
        try:
            notion = AsyncClient(auth=api_key)
            results = await notion.search(query=args.query, sort={"direction": "descending", "timestamp": "last_edited_time"})
            
            output = []
            for item in results.get("results", []):
                title = "Untitled"
                try:
                    if "properties" in item:
                        for prop_name, prop_data in item["properties"].items():
                            if prop_data.get("type") == "title":
                                title_arr = prop_data.get("title", [])
                                if title_arr:
                                    title = title_arr[0].get("plain_text", "Untitled")
                                break
                except:
                    pass
                
                output.append(f"- Page ID: '{item['id']}' | Title: '{title}' | URL: {item.get('url', 'N/A')}")
                
            if not output:
                return f"No Notion search results found for '{args.query}'."
            return f"Notion search results for '{args.query}':\n" + "\n".join(output)
        except Exception as e:
            return f"Error communicating with Notion: {str(e)}"

class NotionReadArgs(BaseModel):
    page_id: str = Field(description="The Notion Page ID to read.")

class ReadNotionPageTool(BaseTool):
    name = "read_notion_page"
    description = "Read the text content of a specific Notion page given its ID."
    args_schema = NotionReadArgs
    
    async def run(self, args: NotionReadArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("NOTION_API_KEY")
        if not api_key or api_key == "your_notion_api_key_here":
            return "Error: NOTION_API_KEY is not set."
            
        try:
            notion = AsyncClient(auth=api_key)
            blocks = []
            cursor = None
            while True:
                response = await notion.blocks.children.list(block_id=args.page_id, start_cursor=cursor)
                blocks.extend(response.get("results", []))
                cursor = response.get("next_cursor")
                if not cursor:
                    break
                    
            text_content = []
            for block in blocks:
                block_type = block.get("type", "")
                if block_type and block_type in block:
                    rich_texts = block[block_type].get("rich_text", [])
                    for rt in rich_texts:
                        text_content.append(rt.get("plain_text", ""))
                    text_content.append("\n")
            
            content = "".join(text_content).strip()
            return f"Content for Notion page {args.page_id}:\n{content}" if content else f"No text content found on page {args.page_id}."
        except Exception as e:
             return f"Error reading Notion page: {str(e)}"

class TavilySearchArgs(BaseModel):
    query: str = Field(description="The search string.")

class TavilySearchTool(BaseTool):
    name = "web_search_tavily"
    description = "Perform a general web search using Tavily API."
    args_schema = TavilySearchArgs
    
    async def run(self, args: TavilySearchArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key or api_key == "your_tavily_api_key_here":
             return "Error: TAVILY_API_KEY is not set."
             
        try:
            client = AsyncTavilyClient(api_key=api_key)
            response = await client.search(query=args.query, search_depth="advanced")
            
            output = []
            for result in response.get("results", []):
                 output.append(f"Title: {result.get('title')}\nURL: {result.get('url')}\nContent: {result.get('content')}\n---")
                 
            return f"Tavily Search Results for '{args.query}':\n\n" + "\n".join(output)
        except Exception as e:
            return f"Error executing Tavily search: {str(e)}"

class FirecrawlArgs(BaseModel):
    url: str = Field(description="The URL to scrape.")

class FirecrawlTool(BaseTool):
    name = "crawl_website_firecrawl"
    description = "Scrape and extract the text content of a specific URL using Firecrawl."
    args_schema = FirecrawlArgs
    
    async def run(self, args: FirecrawlArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key or api_key == "your_firecrawl_api_key_here":
             return "Error: FIRECRAWL_API_KEY is not set."
             
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"url": args.url, "formats": ["markdown"]},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                markdown = data.get("data", {}).get("markdown", "No markdown content extracted.")
                return f"Firecrawl extract for {args.url}:\n\n{markdown}"
        except Exception as e:
            return f"Error executing Firecrawl scrape: {str(e)}"
