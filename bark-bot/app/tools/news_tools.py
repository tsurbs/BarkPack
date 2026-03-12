import os
import httpx
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

NEWS_API_BASE_URL = "https://newsapi.org/v2"

class SearchNewsArgs(BaseModel):
    query: str = Field(description="Keywords or phrases to search for in the articles.")
    language: str = Field(default="en", description="The 2-letter ISO-639-1 code of the language you want to get headlines for.")
    sort_by: str = Field(default="publishedAt", description="The order to sort the articles in. Possible options: relevancy, popularity, publishedAt.")

class SearchNewsTool(BaseTool):
    """
    Search for news articles using the News API.
    """
    name = "search_news"
    description = "Search for news articles on a specific topic using keywords or phrases."
    args_schema = SearchNewsArgs

    async def run(self, args: SearchNewsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            return "Error: NEWS_API_KEY not found in environment."

        params = {
            "q": args.query,
            "language": args.language,
            "sortBy": args.sort_by,
            "apiKey": api_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{NEWS_API_BASE_URL}/everything", params=params)
                response.raise_for_status()
                data = response.json()
                
                articles = data.get("articles", [])
                if not articles:
                    return f"No articles found for query: {args.query}"

                results = []
                for art in articles[:5]:  # Limit to 5 results for brevity
                    results.append(f"Title: {art['title']}\nSource: {art['source']['name']}\nAuthor: {art.get('author') or 'N/A'}\nURL: {art['url']}\nDescription: {art.get('description') or 'No description available.'}\n")

                return "\n---\n".join(results)
            except httpx.HTTPStatusError as e:
                return f"Error from News API: {e.response.text}"
            except Exception as e:
                return f"An unexpected error occurred: {str(e)}"

class GetTopHeadlinesArgs(BaseModel):
    category: Optional[str] = Field(default=None, description="The category you want to get headlines for. Possible options: business, entertainment, general, health, science, sports, technology.")
    country: str = Field(default="us", description="The 2-letter ISO 3166-1 code of the country you want to get headlines for.")
    language: str = Field(default="en", description="The 2-letter ISO-639-1 code of the language you want to get headlines for.")

class GetTopHeadlinesTool(BaseTool):
    """
    Get the top headlines for a country or category.
    """
    name = "get_top_headlines"
    description = "Retrieve the latest top headlines, optionally filtered by category or country."
    args_schema = GetTopHeadlinesArgs

    async def run(self, args: GetTopHeadlinesArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            return "Error: NEWS_API_KEY not found in environment."

        params = {
            "country": args.country,
            "language": args.language,
            "apiKey": api_key
        }
        if args.category:
            params["category"] = args.category

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{NEWS_API_BASE_URL}/top-headlines", params=params)
                response.raise_for_status()
                data = response.json()
                
                articles = data.get("articles", [])
                if not articles:
                    return "No top headlines found."

                results = []
                for art in articles[:10]:  # Limit to 10 headlines
                    results.append(f"- {art['title']} ({art['source']['name']}) - {art['url']}")

                return "Top Headlines:\n" + "\n".join(results)
            except httpx.HTTPStatusError as e:
                return f"Error from News API: {e.response.text}"
            except Exception as e:
                return f"An unexpected error occurred: {str(e)}"
