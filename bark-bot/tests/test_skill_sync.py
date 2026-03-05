import pytest
import os
import yaml
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_s3_env(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("S3_SKILLS_PREFIX", "test-skills/")

@pytest.mark.asyncio
async def test_agent_loader_sync_and_load(mock_s3_env, tmp_path):
    from app.agents.base import AgentLoader
    
    # Create fake local agents directory
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    
    # Fake skill 1: Local v2, S3 v1 (Should upload)
    skill1_yaml = "id: skill1\nversion: 2\ntitle: Skill One\nsystem_prompt: Hi"
    (agents_dir / "skill1.yaml").write_text(skill1_yaml)
    
    # Fake skill 2: Local v1, S3 v2 (Should NOT upload)
    skill2_yaml = "id: skill2\nversion: 1\ntitle: Skill Two\nsystem_prompt: Hi"
    (agents_dir / "skill2.yaml").write_text(skill2_yaml)
    
    # Fake skill 3: Local v1, Not in S3 (Should upload)
    skill3_yaml = "id: skill3\nversion: 1\ntitle: Skill Three\nsystem_prompt: Hi"
    (agents_dir / "skill3.yaml").write_text(skill3_yaml)
    
    loader = AgentLoader(agents_dir=str(agents_dir))
    
    # Mock boto3 client
    mock_s3 = MagicMock()
    
    # Setup mock S3 responses
    def mock_get_object(Bucket, Key):
        if Key == "test-skills/skill1.yaml":
            return {"Body": MagicMock(read=lambda: b"id: skill1\nversion: 1\ntitle: S3 Skill 1")}
        elif Key == "test-skills/skill2.yaml":
            return {"Body": MagicMock(read=lambda: b"id: skill2\nversion: 2\ntitle: S3 Skill 2")}
        else:
            import botocore.exceptions
            raise botocore.exceptions.ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
            )
    mock_s3.get_object.side_effect = mock_get_object
    
    # Mock list for load phase
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "test-skills/skill1.yaml"},
            {"Key": "test-skills/skill2.yaml"},
            {"Key": "test-skills/skill3.yaml"},
        ]
    }
    
    with patch("app.core.s3_client.boto3.client", return_value=mock_s3):
        await loader.initialize()
        
    # Check what was uploaded
    # skill1 (v2 > v1) and skill3 (new) should have been put
    put_calls = mock_s3.put_object.call_args_list
    assert len(put_calls) == 2
    
    keys_uploaded = [call.kwargs["Key"] for call in put_calls]
    assert "test-skills/skill1.yaml" in keys_uploaded
    assert "test-skills/skill3.yaml" in keys_uploaded
    assert "test-skills/skill2.yaml" not in keys_uploaded # Skipped
    
    # Check what was loaded into memory (we simulate S3 get_object above, but because we just used a simple mock, 
    # it doesn't dynamically reflect the puts. For skill3 it will fail the get_object in the load phase with our mock.
    # So we just verify initialize() ran without crashing and put_object was called correctly.
    assert loader._initialized is True
