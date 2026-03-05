import os
import yaml
import logging
import botocore.exceptions
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from app.core.s3_client import get_s3_client, get_bucket_name, get_skills_prefix

logger = logging.getLogger(__name__)


class Agent(BaseModel):
    """
    Standard schema for a dynamically loaded Agent.
    """
    id: str
    version: int = 1
    name: str = Field(alias="title", default="Agent")
    description: str = ""
    system_prompt: str
    skill_prompt: Optional[str] = None
    active_tools: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class AgentLoader:
    """
    Loads agents from S3. On startup, syncs local YAML agent definitions
    to S3 if they are newer or missing, then loads all agents from S3 as
    the runtime source of truth.
    """
    def __init__(self, agents_dir: str = "app/agents"):
        self.agents_dir = agents_dir
        self.agents: Dict[str, Agent] = {}
        self._initialized = False

    async def initialize(self):
        """
        Full async startup sequence:
        1. Sync local agent YAMLs to S3 (upload if newer or missing)
        2. Load all agents from S3
        """
        if self._initialized:
            return
        await self._sync_local_to_s3()
        await self._load_all_from_s3()
        self._initialized = True
        logger.info(f"AgentLoader initialized with {len(self.agents)} agents from S3")

    # ------------------------------------------------------------------
    # Sync: local → S3
    # ------------------------------------------------------------------

    async def _sync_local_to_s3(self):
        """Upload local YAML agents to S3 if they don't exist or have a higher version."""
        if not os.path.exists(self.agents_dir):
            logger.warning(f"Local agents dir '{self.agents_dir}' not found, skipping sync")
            return

        s3 = get_s3_client()
        bucket = get_bucket_name()
        prefix = get_skills_prefix()

        for entry in os.scandir(self.agents_dir):
            if not entry.is_file() or not entry.name.endswith(".yaml"):
                continue

            with open(entry.path, "r") as f:
                local_yaml = f.read()
                local_config = yaml.safe_load(local_yaml)

            agent_id = local_config.get("id", entry.name.replace(".yaml", ""))
            local_version = local_config.get("version", 1)
            s3_key = f"{prefix}{agent_id}.yaml"

            # Check if it already exists in S3
            try:
                s3_obj = s3.get_object(Bucket=bucket, Key=s3_key)
                s3_yaml = s3_obj["Body"].read().decode("utf-8")
                s3_config = yaml.safe_load(s3_yaml)
                s3_version = s3_config.get("version", 0)

                if local_version > s3_version:
                    s3.put_object(Bucket=bucket, Key=s3_key, Body=local_yaml.encode("utf-8"), ContentType="text/yaml")
                    logger.info(f"Uploaded '{agent_id}' to S3 (local v{local_version} > S3 v{s3_version})")
                else:
                    logger.info(f"Skipping '{agent_id}' (S3 v{s3_version} >= local v{local_version})")
            except botocore.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                    s3.put_object(Bucket=bucket, Key=s3_key, Body=local_yaml.encode("utf-8"), ContentType="text/yaml")
                    logger.info(f"Uploaded '{agent_id}' to S3 (new skill)")
                else:
                    logger.warning(f"S3 check failed for '{agent_id}', uploading: {e}")
                    try:
                        s3.put_object(Bucket=bucket, Key=s3_key, Body=local_yaml.encode("utf-8"), ContentType="text/yaml")
                        logger.info(f"Uploaded '{agent_id}' to S3 (fallback)")
                    except Exception as upload_err:
                        logger.error(f"Failed to upload '{agent_id}' to S3: {upload_err}")
            except Exception as e:
                # If GetObject fails for other reasons (bucket missing, etc.), upload anyway
                logger.warning(f"S3 check failed for '{agent_id}', uploading: {e}")
                try:
                    s3.put_object(Bucket=bucket, Key=s3_key, Body=local_yaml.encode("utf-8"), ContentType="text/yaml")
                    logger.info(f"Uploaded '{agent_id}' to S3 (fallback)")
                except Exception as upload_err:
                    logger.error(f"Failed to upload '{agent_id}' to S3: {upload_err}")

    # ------------------------------------------------------------------
    # Load: S3 → memory
    # ------------------------------------------------------------------

    async def _load_all_from_s3(self):
        """Load all agent YAMLs from the S3 skills prefix into memory."""
        s3 = get_s3_client()
        bucket = get_bucket_name()
        prefix = get_skills_prefix()

        try:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        except Exception as e:
            logger.error(f"Failed to list S3 skills: {e}. Falling back to local load.")
            self._load_all_local()
            return

        if "Contents" not in response:
            logger.warning("No skills found in S3. Falling back to local load.")
            self._load_all_local()
            return

        for obj in response["Contents"]:
            key = obj["Key"]
            if not key.endswith(".yaml"):
                continue
            try:
                s3_obj = s3.get_object(Bucket=bucket, Key=key)
                yaml_content = s3_obj["Body"].read().decode("utf-8")
                config = yaml.safe_load(yaml_content)
                self._register_agent(config, source=f"s3://{bucket}/{key}")
            except Exception as e:
                logger.error(f"Failed to load skill from S3 key '{key}': {e}")

    def _load_all_local(self):
        """Fallback: load agents from local YAML files."""
        if not os.path.exists(self.agents_dir):
            return
        for entry in os.scandir(self.agents_dir):
            if entry.is_file() and entry.name.endswith(".yaml"):
                with open(entry.path, "r") as f:
                    config = yaml.safe_load(f)
                self._register_agent(config, source=entry.path)

    def _register_agent(self, config: dict, source: str = "unknown"):
        """Create an Agent from a config dict and register it."""
        agent_id = config.get("id", "unknown")
        agent = Agent(
            id=agent_id,
            version=config.get("version", 1),
            name=config.get("name", config.get("title", agent_id)),
            description=config.get("description", ""),
            system_prompt=config.get("system_prompt", "You are a helpful assistant."),
            skill_prompt=config.get("skill_prompt", config.get("system_prompt", "You are a helpful assistant.")),
            active_tools=config.get("active_tools", [])
        )
        self.agents[agent_id] = agent
        logger.debug(f"Registered agent '{agent_id}' v{agent.version} from {source}")

    # ------------------------------------------------------------------
    # CRUD for runtime skill management
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    async def save_skill_to_s3(self, yaml_content: str) -> str:
        """Save a skill YAML to S3 and register it in memory. Returns the agent ID."""
        config = yaml.safe_load(yaml_content)
        agent_id = config.get("id")
        if not agent_id:
            raise ValueError("Skill YAML must contain an 'id' field.")

        s3 = get_s3_client()
        bucket = get_bucket_name()
        prefix = get_skills_prefix()
        s3_key = f"{prefix}{agent_id}.yaml"

        s3.put_object(Bucket=bucket, Key=s3_key, Body=yaml_content.encode("utf-8"), ContentType="text/yaml")
        self._register_agent(config, source=f"s3://{bucket}/{s3_key}")
        logger.info(f"Saved skill '{agent_id}' to S3 and registered in memory")
        return agent_id

    async def delete_skill_from_s3(self, agent_id: str) -> bool:
        """Delete a skill from S3 and unregister it from memory."""
        s3 = get_s3_client()
        bucket = get_bucket_name()
        prefix = get_skills_prefix()
        s3_key = f"{prefix}{agent_id}.yaml"

        try:
            s3.delete_object(Bucket=bucket, Key=s3_key)
        except Exception as e:
            logger.error(f"Failed to delete skill '{agent_id}' from S3: {e}")
            return False

        self.agents.pop(agent_id, None)
        logger.info(f"Deleted skill '{agent_id}' from S3 and memory")
        return True

    async def get_skill_yaml_from_s3(self, agent_id: str) -> Optional[str]:
        """Retrieve the raw YAML content of a skill from S3."""
        s3 = get_s3_client()
        bucket = get_bucket_name()
        prefix = get_skills_prefix()
        s3_key = f"{prefix}{agent_id}.yaml"

        try:
            s3_obj = s3.get_object(Bucket=bucket, Key=s3_key)
            return s3_obj["Body"].read().decode("utf-8")
        except Exception:
            return None

    # Legacy synchronous method for backward compat during import
    def load_all(self):
        """Synchronous local-only load. Use initialize() for full S3 flow."""
        self._load_all_local()
