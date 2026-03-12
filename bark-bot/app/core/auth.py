import os
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from jwt import PyJWKClient

from app.models.user import User

security = HTTPBearer(auto_error=False)

OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")

# Caches the JWKS locally
if OIDC_ISSUER_URL:
    jwks_url = f"{OIDC_ISSUER_URL.rstrip('/')}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_url)
else:
    jwks_client = None

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> User:
    """
    Dependency to extract and validate an OIDC JWT from the Authorization header.
    Returns the canonical internal User.
    """
    # If no OIDC is configured, allow mock dev user (DANGER IN PROD)
    if not OIDC_ISSUER_URL or not OIDC_CLIENT_ID:
        return User(id="dev-user-id", email="dev@example.com", name="Dev User", roles=["admin"])

    if not credentials:
        print("Auth failed: No credentials provided in Authorization header")
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    
    # If no OIDC is configured, allow mock dev user (DANGEROUS IN PROD, used for local dev only)
    if not OIDC_ISSUER_URL or not OIDC_CLIENT_ID:
        return User(id="dev-user-id", email="dev@example.com", name="Dev User", roles=["admin"])
        
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        print(f"Decoding token with audience {OIDC_CLIENT_ID} and issuer {OIDC_ISSUER_URL}")
        
        # Verify without audience first to debug what the token actually contains
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        print(f"Unverified token payload: {unverified_payload}")

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_CLIENT_ID,
            issuer=OIDC_ISSUER_URL
        )
        
        # Build our internal user from the OIDC payload
        user = User(
            id=payload.get("sub"),
            email=payload.get("email"),
            name=payload.get("name", payload.get("preferred_username", "Unknown User")),
            roles=payload.get("roles", [])
        )

        # Auto-assign admin role from env var
        admin_emails_raw = os.getenv("ADMIN_EMAILS", "")
        if admin_emails_raw:
            admin_emails = [e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()]
            if user.email and user.email.lower() in admin_emails:
                if "admin" not in user.roles:
                    user.roles.append("admin")
        
        return user
    except jwt.ExpiredSignatureError as e:
        print(f"Auth failed: Token expired - {e}")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError as e:
        print(f"Auth failed: PyJWTError - {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        print(f"Auth failed: Unexpected error - {e}")
        raise HTTPException(status_code=401, detail=f"Unexpected auth error: {str(e)}")

def get_db_session():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user_with_db_roles(
    token_user: User = Depends(get_current_user),
    db: "Session" = Depends(get_db_session)
) -> User:
    """
    Enriches the standard User with roles from the database.
    """
    from app.db.models import DBUserRole, DBRole

    # Get roles from DB
    user_roles = db.query(DBRole.name).join(
        DBUserRole, DBRole.id == DBUserRole.role_id
    ).filter(
        DBUserRole.user_id == token_user.id
    ).all()
    
    # Extract role names
    db_role_names = [role[0] for role in user_roles]
    
    # Merge with existing roles (e.g. from OIDC token)
    all_roles = list(set(token_user.roles + db_role_names))
    token_user.roles = all_roles
    
    return token_user

def require_role(required_role: str):
    """
    Dependency to enforce a specific role requirement.
    """
    from fastapi import Depends, HTTPException
    
    async def role_checker(user: User = Depends(get_current_user_with_db_roles)):
        if required_role not in user.roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Operation requires role: {required_role}"
            )
        return user
        
    return role_checker
