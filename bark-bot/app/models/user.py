from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any

class User(BaseModel):
    """
    Standard Internal User Identity for Bark Bot.
    This is what agents and tools see as the active caller.
    """
    id: str  # The unique standard ID (e.g. UUID from our DB or the "sub" from OIDC)
    email: Optional[str] = None
    name: Optional[str] = None
    roles: List[str] = []
    
class IdentityMap(BaseModel):
    """
    Maps surface-specific identities to the standard internal User ID.
    Example: slack_id -> standard_user_id
    """
    internal_user_id: str
    slack_user_id: Optional[str] = None
    email_address: Optional[str] = None
