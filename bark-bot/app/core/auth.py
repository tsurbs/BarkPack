import os
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from app.models.user import User

security = HTTPBearer()

OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")

# Caches the JWKS locally
if OIDC_ISSUER_URL:
    jwks_url = f"{OIDC_ISSUER_URL.rstrip('/')}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_url)
else:
    jwks_client = None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """
    Dependency to extract and validate an OIDC JWT from the Authorization header.
    Returns the canonical internal User.
    """
    token = credentials.credentials
    
    # If no OIDC is configured, allow mock dev user (DANGEROUS IN PROD, used for local dev only)
    if not OIDC_ISSUER_URL or not OIDC_CLIENT_ID:
        return User(id="dev-user-id", email="dev@example.com", name="Dev User", roles=["admin"])
        
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_CLIENT_ID,
            issuer=OIDC_ISSUER_URL
        )
        
        # Build our internal user from the OIDC payload
        return User(
            id=payload.get("sub"),
            email=payload.get("email"),
            name=payload.get("name", payload.get("preferred_username", "Unknown User")),
            roles=payload.get("roles", [])
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
