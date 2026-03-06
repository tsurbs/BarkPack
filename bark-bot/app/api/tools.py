from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import DBTool
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/v1/tools")

class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    toolType: str
    content: str
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True

class CreateToolRequest(BaseModel):
    name: str
    description: str
    toolType: str
    content: str

class UpdateToolRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    toolType: Optional[str] = None
    content: Optional[str] = None

@router.get("", response_model=List[ToolResponse])
async def list_tools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBTool).order_by(DBTool.created_at.desc()))
    db_tools = result.scalars().all()
    
    # Map snake_case model to camelCase response
    return [
        ToolResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            toolType=t.tool_type,
            content=t.content,
            createdAt=t.created_at.isoformat() if t.created_at else "",
            updatedAt=t.updated_at.isoformat() if t.updated_at else ""
        ) for t in db_tools
    ]

@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBTool).where(DBTool.id == tool_id))
    tool = result.scalars().first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
        
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        toolType=tool.tool_type,
        content=tool.content,
        createdAt=tool.created_at.isoformat() if tool.created_at else "",
        updatedAt=tool.updated_at.isoformat() if tool.updated_at else ""
    )

@router.post("", response_model=ToolResponse)
async def create_tool(req: CreateToolRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Basic check for unique name
    result = await db.execute(select(DBTool).where(DBTool.name == req.name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Tool with this name already exists")

    new_tool = DBTool(
        name=req.name,
        description=req.description,
        tool_type=req.toolType,
        content=req.content
    )
    db.add(new_tool)
    await db.commit()
    await db.refresh(new_tool)

    return ToolResponse(
        id=new_tool.id,
        name=new_tool.name,
        description=new_tool.description,
        toolType=new_tool.tool_type,
        content=new_tool.content,
        createdAt=new_tool.created_at.isoformat() if new_tool.created_at else "",
        updatedAt=new_tool.updated_at.isoformat() if new_tool.updated_at else ""
    )

@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: str, req: UpdateToolRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(DBTool).where(DBTool.id == tool_id))
    tool = result.scalars().first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
        
    if req.name is not None:
        # Check uniqueness if changing
        if req.name != tool.name:
            dup = await db.execute(select(DBTool).where(DBTool.name == req.name))
            if dup.scalars().first():
                raise HTTPException(status_code=400, detail="Tool with this name already exists")
        tool.name = req.name
        
    if req.description is not None:
        tool.description = req.description
    if req.toolType is not None:
        tool.tool_type = req.toolType
    if req.content is not None:
        tool.content = req.content

    await db.commit()
    await db.refresh(tool)

    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        toolType=tool.tool_type,
        content=tool.content,
        createdAt=tool.created_at.isoformat() if tool.created_at else "",
        updatedAt=tool.updated_at.isoformat() if tool.updated_at else ""
    )

@router.delete("/{tool_id}")
async def delete_tool(tool_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(DBTool).where(DBTool.id == tool_id))
    tool = result.scalars().first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
        
    if tool.tool_type == "native":
        raise HTTPException(status_code=400, detail="Cannot delete native tools via API")
        
    await db.delete(tool)
    await db.commit()
    return {"status": "ok"}
