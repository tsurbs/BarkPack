from app.tools.base import BaseTool
from typing import List, Dict

def get_openai_tools_schema(tools: List[BaseTool]) -> List[Dict]:
    """
    Converts a list of BaseTool instances into OpenAI's required JSON Schema format.
    """
    openai_tools = []
    for tool in tools:
        schema = tool.args_schema.model_json_schema()
        # Clean up Pydantic specifics
        schema.pop("title", None)
        
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": schema
            }
        })
    return openai_tools
