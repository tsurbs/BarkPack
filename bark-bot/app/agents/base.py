import os
import yaml
import importlib.util
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.tools.base import BaseTool

class Agent(BaseModel):
    """
    Standard schema for a dynamically loaded Agent.
    """
    id: str
    name: str = Field(alias="title", default="Agent") # Handle both 'title' and 'name'
    description: str = ""
    system_prompt: str
    skill_prompt: Optional[str] = None # Fragment used when loading as a skill
    active_tools: List[str] = Field(default_factory=list) # List of tool name strings

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class AgentLoader:
    """
    Dynamically loads agents from the workspace `agents/` directory.
    """
    def __init__(self, agents_dir: str = "app/agents"):
        self.agents_dir = agents_dir
        self.agents: Dict[str, Agent] = {}
        
    def load_all(self):
        """Scan the agents directory and load valid agents."""
        if not os.path.exists(self.agents_dir):
            os.makedirs(self.agents_dir, exist_ok=True)
            return

        for entry in os.scandir(self.agents_dir):
            if entry.is_file() and entry.name.endswith(".yaml"):
                self._load_agent(entry.path)
                
    def _load_agent(self, file_path: str):
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)
            
        agent_id = config.get("id", os.path.basename(file_path).replace(".yaml", ""))
        
        agent = Agent(
            id=agent_id,
            name=config.get("name", config.get("title", agent_id)),
            description=config.get("description", ""),
            system_prompt=config.get("system_prompt", "You are a helpful assistant."),
            skill_prompt=config.get("skill_prompt", config.get("system_prompt", "You are a helpful assistant.")),
            active_tools=config.get("active_tools", [])
        )
        self.agents[agent_id] = agent
        
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)
