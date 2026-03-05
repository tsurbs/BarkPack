import yaml
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool


class ManageSkillArgs(BaseModel):
    action: str = Field(description="The action to perform. One of: 'list', 'get', 'create', 'update', 'delete'.")
    skill_id: Optional[str] = Field(default=None, description="The ID of the skill to operate on. Required for 'get', 'update', and 'delete'.")
    skill_yaml: Optional[str] = Field(default=None, description="The full YAML content for the skill. Required for 'create' and 'update'. Must include 'id', 'version', 'name', 'system_prompt', 'skill_prompt', and 'active_tools' fields.")


class ManageSkillTool(BaseTool):
    """
    Manage skills in the S3 skill store. Allows listing, reading, creating,
    updating, and deleting skills at runtime.
    """
    name = "manage_skill"
    description = (
        "Manage bot skills stored in S3. Actions:\n"
        "- 'list': List all available skills with IDs and versions.\n"
        "- 'get': Read the full YAML of a skill by ID.\n"
        "- 'create': Create a new skill from YAML content.\n"
        "- 'update': Update an existing skill with new YAML content (bumps version).\n"
        "- 'delete': Delete a skill by ID."
    )
    args_schema = ManageSkillArgs

    def __init__(self, agent_loader=None):
        self._agent_loader = agent_loader

    async def run(self, args: ManageSkillArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if self._agent_loader is None:
            return "Error: ManageSkillTool has no agent_loader reference."

        action = args.action.lower()
        if action == "list":
            return self._list_skills()
        elif action == "get":
            return await self._get_skill(args.skill_id)
        elif action == "create":
            return await self._create_skill(args.skill_yaml)
        elif action == "update":
            return await self._update_skill(args.skill_id, args.skill_yaml)
        elif action == "delete":
            return await self._delete_skill(args.skill_id)
        else:
            return f"Error: Unknown action '{action}'. Valid actions: list, get, create, update, delete."

    def _list_skills(self) -> str:
        agents = self._agent_loader.agents
        if not agents:
            return "No skills are currently loaded."
        lines = ["Available Skills:"]
        for agent_id, agent in sorted(agents.items()):
            lines.append(f"- **{agent.name}** (id: `{agent_id}`, v{agent.version}) — {agent.description}")
        return "\n".join(lines)

    async def _get_skill(self, skill_id: Optional[str]) -> str:
        if not skill_id:
            return "Error: 'skill_id' is required for the 'get' action."
        yaml_content = await self._agent_loader.get_skill_yaml_from_s3(skill_id)
        if yaml_content is None:
            return f"Error: Skill '{skill_id}' not found in S3."
        return f"```yaml\n{yaml_content}```"

    async def _create_skill(self, skill_yaml: Optional[str]) -> str:
        if not skill_yaml:
            return "Error: 'skill_yaml' is required for the 'create' action."
        try:
            config = yaml.safe_load(skill_yaml)
        except yaml.YAMLError as e:
            return f"Error: Invalid YAML: {e}"

        skill_id = config.get("id")
        if not skill_id:
            return "Error: Skill YAML must contain an 'id' field."

        if skill_id in self._agent_loader.agents:
            return f"Error: Skill '{skill_id}' already exists. Use 'update' instead."

        try:
            created_id = await self._agent_loader.save_skill_to_s3(skill_yaml)
            return f"Successfully created skill '{created_id}' (v{config.get('version', 1)})."
        except Exception as e:
            return f"Error creating skill: {e}"

    async def _update_skill(self, skill_id: Optional[str], skill_yaml: Optional[str]) -> str:
        if not skill_id:
            return "Error: 'skill_id' is required for the 'update' action."
        if not skill_yaml:
            return "Error: 'skill_yaml' is required for the 'update' action."
        try:
            config = yaml.safe_load(skill_yaml)
        except yaml.YAMLError as e:
            return f"Error: Invalid YAML: {e}"

        yaml_id = config.get("id")
        if yaml_id and yaml_id != skill_id:
            return f"Error: YAML 'id' field ('{yaml_id}') does not match skill_id ('{skill_id}')."

        if not yaml_id:
            config["id"] = skill_id
            skill_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False)

        try:
            await self._agent_loader.save_skill_to_s3(skill_yaml)
            return f"Successfully updated skill '{skill_id}' to v{config.get('version', 1)}."
        except Exception as e:
            return f"Error updating skill: {e}"

    async def _delete_skill(self, skill_id: Optional[str]) -> str:
        if not skill_id:
            return "Error: 'skill_id' is required for the 'delete' action."
        success = await self._agent_loader.delete_skill_from_s3(skill_id)
        if success:
            return f"Successfully deleted skill '{skill_id}' from S3."
        else:
            return f"Error: Failed to delete skill '{skill_id}'."
