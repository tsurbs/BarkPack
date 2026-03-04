# Bark Bot Implementation Plan

This document outlines the phased implementation plan for Bark Bot, a multi-modal, agentic AI backend powered by OpenRouter. The implementation builds outward from the core logic to user interactions, and finally to advanced autonomous capabilities.

## Phase 1: Core Foundation & LLM Integration
The goal of this phase is to establish basic text-in, text-out capabilities using OpenRouter.

### Proposed Changes
- **[app/core/llm.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/llm.py)**: [NEW] OpenRouter client wrapper using the standard [openai](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/utils.py#4-23) Python SDK configured for OpenRouter to handle API calls.
- **[app/core/orchestrator.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/orchestrator.py)**: [NEW] Initial version of the orchestrator. At this stage, it will act as a pass-through to OpenRouter with a basic system prompt.
- **[app/models/schemas.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/schemas.py)**: [NEW] Pydantic models for generic requests and responses (e.g., [ChatRequest](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/schemas.py#8-12), [ChatResponse](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/schemas.py#13-16)).

## Phase 2: User Management & Surfaces
Transform the core into a usable chatbot accessible through multiple interfaces, secured by OIDC.

### Proposed Changes
- **[app/core/auth.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/auth.py)**: [NEW] OIDC middleware/dependency for FastAPI to validate JWTs.
- **[app/models/user.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/user.py)**: [NEW] User identity models and the Identity Map for cross-surface resolution.
- **[app/surfaces/base.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/base.py)**: [NEW] Abstract base class defining [receive_event()](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/base.py#9-16), [authenticate()](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/base.py#17-25), and [respond()](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/base.py#26-32).
- **[app/surfaces/web.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/web.py)**: [NEW] REST endpoints conforming to the OpenAI standard (`/v1/chat/completions`), to be consumed by a separate frontend.
- **[app/surfaces/cli.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/cli.py)**: [NEW] Terminal interface for quick local testing.
- **[app/surfaces/slack.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/slack.py)**: [NEW] Slack Event API receiver.

## Phase 3: Agentic Functionality
Introduce dynamic agents, tools, and the ability for the orchestrator to route intents or hand off tasks.

### Proposed Changes
- **[app/agents/base.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/agents/base.py)**: [NEW] Base agent class and dynamic loader logic to read from workspace `agents/`.
- **[app/tools/base.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/base.py)**: [NEW] Base tool interface with RBAC/ABAC permission checks.
- **[app/tools/core_tools.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/core_tools.py)**: [NEW] Implementation of basic tools (e.g., mathematical execution, web search).
- **[app/core/orchestrator.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/orchestrator.py)**: [MODIFY] Update to use an LLM router to classify intent, select the appropriate agent from the loaded pool, and manage agent handoffs via specialized tools.

## Phase 4: Memory & Persistence
Add stateful long-term memory using Postgres and `pgvector`.

### Proposed Changes
- **[app/db/session.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/db/session.py)**: [NEW] Database connection and session management (SQLAlchemy).
- **[app/db/models.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/db/models.py)**: [NEW] SQLAlchemy models for [Conversation](file:///Users/tsumacpro/BarkPack/bark-bot/app/db/models.py#22-27), [Message](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/schemas.py#4-7), [User](file:///Users/tsumacpro/BarkPack/bark-bot/app/models/user.py#4-13), and [UserProfile](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/summarization_tools.py#46-69).
- **[app/memory/history.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/memory/history.py)**: [NEW] Service to log conversation turns and retrieve recent window.
- **[app/memory/vector_store.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/memory/vector_store.py)**: [NEW] Semantic search across agent posts, logs, and historical context.

## Phase 5: Building Core Agents
Deploy specific "Skills" by writing personas and mapping tools to the `agents/` directory.

### Proposed Agents
1. **Google Workspace Agent (`agents/google_workspace`)**
   - **Tools:** `read_gmail_messages`, `send_gmail`, `create_calendar_event`, `find_calendar_freebusy`, `search_drive_files`, `modify_drive_permissions`, `create_google_doc`, `update_google_sheet`, `subscribe_workspace_events`, `manage_cloud_identity_groups`
   - **Role:** Handles provisioning, scheduling, document generation, and tracking across the Google ecosystem utilizing Gmail, Drive, Docs, Sheets, Calendar, and the Admin/Cloud Identity SDKs.

2. **Knowledge Retriever Agent (`agents/knowledge_retriever`)**
   - **Tools:** `search_notion`, `read_notion_page`, `web_search_tavily`, `crawl_website_firecrawl`
   - **Role:** General-purpose knowledge synthesizer. When asked a factual company question, this agent finds the relevant internal wiki (Notion) or extracts external web data using Firecrawl and Tavily.

3. **Data Analyst Agent (`agents/data_analyst`)**
   - **Tools:** `execute_python_script`, `read_csv`, `execute_bash`
   - **Role:** Writes and executes Python code locally using pandas/matplotlib to generate insights from data files provided in the workspace. Can use the bash CLI to run commands, but does not query Postgres directly.

4. **Software Engineer Agent (`agents/software_engineer`)**
   - **Tools:** `execute_bash`, `read_file`, `write_file`, `git_commit`, `git_push`, `railway_deploy`
   - **Role:** Dedicated code writer. Operates safely within the workspace to read repositories, modify code, execute GitOps flows, and deploy applications using the Railway CLI.

5. **Memory/Summarization Agent (`agents/memory_summarizer`)**
   - **Tools:** `summarize_conversation`, `update_user_profile`
   - **Role:** Runs asynchronously to process past logs and build out the long-term semantic memory. **Context Storage:** Summarized attributes will be stored as structured JSON in the new [UserProfile](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/summarization_tools.py#46-69) Postgres table, and standalone factual notes will be persisted in the [AgentPost](file:///Users/tsumacpro/BarkPack/bark-bot/app/db/models.py#36-44) `pgvector` table for semantic retrieval by all other agents.

6. **GitHub Project Manager Agent (`agents/project_manager`)**
   - **Tools:** `search_github_issues`, `create_github_issue`, `update_github_project_status`
   - **Role:** Operates alongside the SWE agent to automatically update ticket statuses, read specs, and manage sprints using GitHub Projects and Issues.

## Phase 6: Real API Integrations
Replace the mock logic in the agent tools with actual third-party API SDK calls.

### Proposed Changes
- **[app/tools/knowledge_tools.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/knowledge_tools.py)**: [MODIFY] Implement standard REST calls to Tavily and Firecrawl using `httpx`. Implement Notion searching/reading using the official Notion SDK or REST.
- **[app/tools/github_tools.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/github_tools.py)**: [MODIFY] Implement GitHub Issue searching, creation, and project board updates using PyGithub or GraphQL.
- **[app/tools/summarization_tools.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/summarization_tools.py)**: [MODIFY] Implement actual `app.memory.profile` summarization logic triggering an OpenRouter call and issuing an `UPDATE` statement to the [UserProfile](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/summarization_tools.py#46-69) Postgres table.
- **[app/tools/google_workspace_tools.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/google_workspace_tools.py)**: [MODIFY] Connect the 10 granular Workspace tools to the `google-api-python-client` using the established OAuth 2.0 refresh token.
- **Dependencies**: [NEW] Add `notion-client`, `httpx`, `PyGithub` (and potentially others) via `uv`.

## Phase 7: S3 / RustFS File Publishing
Allow the Base Agent to upload files to a local S3-compatible object store (RustFS) and generate public links for the user.

### Proposed Changes
- **[docker-compose.yml](file:///Users/tsumacpro/BarkPack/bark-bot/docker-compose.yml)**: [MODIFY] Add `rustfs` service using `rustfs/rustfs:latest` on port 9000 (S3 API). Credentials configured via env vars.
- **`app/tools/s3_tools.py`**: [NEW] Create `UploadToS3Tool` using `boto3`. Uses custom endpoint `http://localhost:9000` to upload files, returning pre-signed URLs.
- **[app/core/orchestrator.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/orchestrator.py)**: [MODIFY] Register the S3 tool.
- **[app/agents/bark_bot.yaml](file:///Users/tsumacpro/BarkPack/bark-bot/app/agents/bark_bot.yaml)**: [MODIFY] Add `upload_to_s3` to the base agent's active tools.

## Recent Enhancements (Autonomous Orchestrator)
- **[app/agents/bark_bot.yaml](file:///Users/tsumacpro/BarkPack/bark-bot/app/agents/bark_bot.yaml)**: [MODIFY] Granted the `bark_bot` access to all 37 tools across the workspace and updated its system prompt to act autonomously, perform tasks directly, and log frequently, only handing off for extremely specialized/complex work.
- **[app/surfaces/slack.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/surfaces/slack.py)**: [MODIFY] Added comprehensive reaction management tracking to ensure that the bot's "thinking" emojis are cleanly removed in a `finally` block once the orchestrator finishes processing.

## User Review Required
> [!IMPORTANT]
> - Do you agree with the proposed directory structure (e.g., `app/core`, `app/surfaces`, `app/agents`)?
> - Should we use the standard [openai](file:///Users/tsumacpro/BarkPack/bark-bot/app/tools/utils.py#4-23) python SDK pointing to OpenRouter's base URL, or write a custom `httpx` client?
> - For the initial Web Surface (Phase 2), do you want a simple HTML template served by FastAPI, or just REST endpoints to be consumed by a separate React/Vue frontend?

## Verification Plan

### Automated Tests
- **Unit Tests (`pytest`)**: Write tests for the [llm.py](file:///Users/tsumacpro/BarkPack/bark-bot/app/core/llm.py) OpenRouter wrapper using `respx` to mock API responses. Check that Pydantic schemas validate correctly.
- **Agent Loading Tests (`pytest`)**: Verify that the dynamic agent loader correctly parses an example `agents/test_agent` directory and constructs the Python object.

### Manual Verification
1. **Phase 1**: Run a quick CLI script `python -m app.core.orchestrator` to verify connectivity to OpenRouter and basic prompt formatting.
2. **Phase 2**: Start the FastAPI server (`uv run uvicorn main:app`) and use the CLI surface. Verify that unauthenticated requests are rejected or trigger an auth challenge.
3. **Phase 3**: Create a dummy "Calculator Agent". Run the CLI surface, ask a math question, and verify the orchestrator routes to the Calculator Agent and successfully executes the tool.
4. **Phase 4**: Connect to a local Postgres instance. Conduct a multi-turn conversation in the CLI surface, close the CLI, reopen it with the same simulated user ID, and verify the bot remembers the previous turns.
