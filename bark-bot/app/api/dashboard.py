from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.auth import get_current_user_with_db_roles, require_role, get_db_session
from app.models.user import User
from app.db.models import DBUserAuth, DBRole, DBUserRole, DBSurfaceCredential

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Pydantic Output Models
class DashboardUser(BaseModel):
    id: str
    name: str
    email: str
    roles: List[str]

class SurfaceCredentialResponse(BaseModel):
    id: str
    surface: str
    created_at: str
    
class CreateSurfaceCredentialRequest(BaseModel):
    surface: str
    token: str

@router.get("/users", response_model=List[DashboardUser])
async def get_all_users(
    admin_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db_session)
):
    """Admin only: List all authenticated users and their assigned roles."""
    users = db.query(DBUserAuth).all()
    
    result = []
    for u in users:
        roles = db.query(DBRole.name).join(DBUserRole, DBRole.id == DBUserRole.role_id).filter(DBUserRole.user_id == u.id).all()
        role_names = [r[0] for r in roles]
        result.append(DashboardUser(id=u.id, name=u.name, email=u.email, roles=role_names))
        
    return result

@router.put("/users/{user_id}/roles/{role_name}")
async def assign_role_to_user(
    user_id: str,
    role_name: str,
    admin_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db_session)
):
    """Admin only: Assign a new role to an existing user."""
    # Find role
    role = db.query(DBRole).filter(DBRole.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # Check if already exists
    existing = db.query(DBUserRole).filter(DBUserRole.user_id == user_id, DBUserRole.role_id == role.id).first()
    if existing:
        return {"status": "Role already assigned"}
        
    new_user_role = DBUserRole(user_id=user_id, role_id=role.id)
    db.add(new_user_role)
    db.commit()
    return {"status": "Role assigned successfully"}
    
@router.delete("/users/{user_id}/roles/{role_name}")
async def revoke_role_from_user(
    user_id: str,
    role_name: str,
    admin_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db_session)
):
    """Admin only: Revoke a role from a user."""
    role = db.query(DBRole).filter(DBRole.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    db.query(DBUserRole).filter(DBUserRole.user_id == user_id, DBUserRole.role_id == role.id).delete()
    db.commit()
    return {"status": "Role revoked successfully"}


@router.get("/credentials", response_model=List[SurfaceCredentialResponse])
async def get_my_surface_credentials(
    current_user: User = Depends(get_current_user_with_db_roles),
    db: Session = Depends(get_db_session)
):
    """Get the active user's surface credentials."""
    creds = db.query(DBSurfaceCredential).filter(DBSurfaceCredential.user_id == current_user.id).all()
    
    return [
        SurfaceCredentialResponse(
            id=c.id, 
            surface=c.surface, 
            created_at=c.created_at.isoformat() if c.created_at else ""
        ) for c in creds
    ]

@router.post("/credentials", response_model=SurfaceCredentialResponse)
async def add_surface_credential(
    req: CreateSurfaceCredentialRequest,
    current_user: User = Depends(get_current_user_with_db_roles),
    db: Session = Depends(get_db_session)
):
    """Add or update a surface token for the current user."""
    existing = db.query(DBSurfaceCredential).filter(
        DBSurfaceCredential.user_id == current_user.id,
        DBSurfaceCredential.surface == req.surface
    ).first()
    
    if existing:
        existing.token = req.token
        db.commit()
        db.refresh(existing)
        return SurfaceCredentialResponse(
            id=existing.id,
            surface=existing.surface,
            created_at=existing.created_at.isoformat() if existing.created_at else ""
        )
        
    new_cred = DBSurfaceCredential(
        user_id=current_user.id,
        surface=req.surface,
        token=req.token
    )
    db.add(new_cred)
    db.commit()
    db.refresh(new_cred)
    
    return SurfaceCredentialResponse(
        id=new_cred.id,
        surface=new_cred.surface,
        created_at=new_cred.created_at.isoformat() if new_cred.created_at else ""
    )

@router.delete("/credentials/{surface}")
async def delete_surface_credential(
    surface: str,
    current_user: User = Depends(get_current_user_with_db_roles),
    db: Session = Depends(get_db_session)
):
    """Delete a surface credential for the active user."""
    db.query(DBSurfaceCredential).filter(
        DBSurfaceCredential.user_id == current_user.id,
        DBSurfaceCredential.surface == surface
    ).delete()
    db.commit()
    return {"status": "Credential deleted successfully"}
