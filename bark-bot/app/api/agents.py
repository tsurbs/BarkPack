from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import yaml

from app.core.auth import get_current_user
from app.models.user import User
from app.core.orchestrator import agent_loader

router = APIRouter(prefix="/v1/agents")

class AgentSummaryResponse(BaseModel):
    id: str
    name: str
    version: int
    description: str

class AgentDetailResponse(BaseModel):
    id: str
    yaml_content: str

class AgentCreateUpdateRequest(BaseModel):
    yaml_content: str

@router.get("", response_model=List[AgentSummaryResponse])
async def list_agents(user: User = Depends(get_current_user)):
    agents = []
    for agent_id, agent in agent_loader.agents.items():
        agents.append(AgentSummaryResponse(
            id=agent.id,
            name=agent.name,
            version=agent.version,
            description=agent.description
        ))
    return sorted(agents, key=lambda a: a.name)

@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(agent_id: str, user: User = Depends(get_current_user)):
    yaml_content = await agent_loader.get_skill_yaml_from_s3(agent_id)
    if yaml_content is None:
        raise HTTPException(status_code=404, detail=f"Agent skill '{agent_id}' not found")
        
    return AgentDetailResponse(id=agent_id, yaml_content=yaml_content)

@router.post("", response_model=AgentSummaryResponse)
async def create_agent(req: AgentCreateUpdateRequest, user: User = Depends(get_current_user)):
    try:
        config = yaml.safe_load(req.yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    agent_id = config.get("id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Skill YAML must contain an 'id' field.")

    if agent_id in agent_loader.agents:
        raise HTTPException(status_code=400, detail=f"Agent '{agent_id}' already exists. Use PUT to update.")

    try:
        saved_id = await agent_loader.save_skill_to_s3(req.yaml_content)
        agent = agent_loader.get_agent(saved_id)
        return AgentSummaryResponse(
            id=agent.id,
            name=agent.name,
            version=agent.version,
            description=agent.description
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")

@router.put("/{agent_id}", response_model=AgentSummaryResponse)
async def update_agent(agent_id: str, req: AgentCreateUpdateRequest, user: User = Depends(get_current_user)):
    try:
        config = yaml.safe_load(req.yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    yaml_id = config.get("id")
    if yaml_id and yaml_id != agent_id:
        raise HTTPException(status_code=400, detail=f"YAML 'id' '{yaml_id}' does not match endpoint '{agent_id}'")
        
    if not yaml_id:
         config["id"] = agent_id
         req.yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False)

    try:
        saved_id = await agent_loader.save_skill_to_s3(req.yaml_content)
        agent = agent_loader.get_agent(saved_id)
        return AgentSummaryResponse(
            id=agent.id,
            name=agent.name,
            version=agent.version,
            description=agent.description
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")

@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: User = Depends(get_current_user)):
    success = await agent_loader.delete_skill_from_s3(agent_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete agent '{agent_id}'")
    return {"status": "ok"}
