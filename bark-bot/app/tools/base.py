from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

class BaseTool(ABC):
    """
    Abstract base class for all Bark Bot tools.
    Provides standard interface and permission gating.
    """
    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel]

    @abstractmethod
    async def run(self, args: BaseModel, user: User, db: Optional[AsyncSession] = None) -> Any:
        """Execute the tool's core logic"""
        pass
        
    async def execute(self, args_dict: Dict[str, Any], user: User, db: Optional[AsyncSession] = None) -> Any:
        """Parse arguments, verify permissions, and run."""
        if not self.check_permissions(user):
            return f"Error: User {user.id} does not have permission to execute tool '{self.name}'."
            
        # Parse and validate arguments against the schema
        try:
            parsed_args = self.args_schema(**args_dict)
        except Exception as e:
            return f"Error parsing arguments for tool '{self.name}': {str(e)}"
            
        return await self.run(parsed_args, user, db)

    def check_permissions(self, user: User) -> bool:
        """
        Default permission check. 
        Override in subclasses for specific RBAC/ABAC logic.
        """
        return True
