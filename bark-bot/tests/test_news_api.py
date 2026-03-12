import asyncio
import os
from dotenv import load_dotenv
from app.tools.news_tools import SearchNewsTool, GetTopHeadlinesTool
from app.models.user import User

async def test_news_tools():
    # Load env vars
    load_dotenv()
    
    # Mock user
    user = User(id="test-user", email="test@example.com")
    
    search_tool = SearchNewsTool()
    headlines_tool = GetTopHeadlinesTool()
    
    print("--- Testing Top Headlines ---")
    headlines_res = await headlines_tool.run(GetTopHeadlinesTool.args_schema(category="technology"), user)
    print(headlines_res)
    
    print("\n--- Testing Search News (Python) ---")
    search_res = await search_tool.run(SearchNewsTool.args_schema(query="Python programming"), user)
    print(search_res)

if __name__ == "__main__":
    asyncio.run(test_news_tools())
