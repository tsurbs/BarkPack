# CONTRIBUTING-LLMS.md - Agent's Guide to BarkPack

Welcome, fellow Agent! This repository is a sophisticated, multi-modal AI ecosystem. To contribute effectively, you must understand our unique "Skill + Tool" architecture and specialized communication protocols.

---

## 🏗️ Project Structure

- **`bark-bot/`**: The FastAPI-based "brain". Handles orchestration, memory, and tool execution.
- **`bark-web/`**: The React-based "face" built with TanStack Start.

---

## 🧠 Agent Architecture (Skills & Tools)

Bark Bot does not just run one LLM loop; it manages a dynamic pool of specialized **Agents** (Skills) that use **Tools**.

### 1. Skills (`bark-bot/app/agents/*.yaml`)
A "Skill" is a persona definition. Agents are loaded dynamically (synced between local storage and S3).
- **Definition**: Each `.yaml` file defines an `id`, `name`, `system_prompt`, and a list of `active_tools`.
- **Dynamic Loading**: `AgentLoader` (in `app/agents/base.py`) syncs these to S3 on startup. When contributing, you can add new YAMLs to define specialized behaviors.

### 2. Tools (`bark-bot/app/tools/`)
Tools are the functional hands of the agents.
- **Base Class**: All tools must inherit from `BaseTool` (`app/tools/base.py`).
- **Implementation**:
    - Require a Pydantic `args_schema` for structured input.
    - Implement an `async def run(...)` method.
    - Support permission gating via `check_permissions(user)`.
- **Types**: 
    - **Native**: Python classes in the repo.
    - **Python**: Dynamic scripts compiled from the DB.
    - **MCP**: Integration with Model Context Protocol servers.

### 3. Tool Registry (`bark-bot/app/tools/registry.py`)
All native tools must be registered in the `NATIVE_TOOLS` map to be available to the Orchestrator.

---

## 🛠️ Unique Capabilities & Protocols

To provide a premium experience, we use several non-standard protocols:

### 1. Communication Protocols
- **File Attachments**: To send a file to the UI (e.g., Slack/Web), return the following string from a tool:
  `__ATTACHMENT__|||/path/to/local/file|||display_name.ext`
- **Silence (No-Reply)**: If a message doesn't require a response (e.g., casual talk or "thanks"), return exactly:
  `__NO_REPLY__`

### 2. Vectorized Memory (`AgentPost`)
Agents share a "bulletin board" for long-term memory.
- Use the `create_agent_post` tool to persist facts or artifacts.
- Use `search_agent_posts` (backed by `pgvector`) to retrieve relevant context from other agents' past work.

### 3. Autonomous Orchestration
The default `bark_bot` agent is an autonomous orchestrator. It can use `load_skill` to delegate complex tasks but is encouraged to solve problems directly using its 37+ tools.

### 4. Context Compression
The orchestrator automatically compresses conversation history using an LLM summary once a token threshold is hit, ensuring we never overflow the context window while maintaining "the gist" of the talk.

---

## 🎨 Frontend Development (`bark-web/`)

- **Tech Stack**: React 19 + TanStack Start (`react-start`, `react-router`, `react-query`).
- **Styling**: Tailwind CSS 4.
- **Formatting**: We use **Biome**. Always run `bun run check` before submitting frontend changes.

---

## 🚀 Workflow & Best Practices

### Environment & Deps
- **Backend**: Use `uv` (e.g., `uv sync`, `uv run ...`).
- **Frontend**: Use `bun` (e.g., `bun install`, `bun dev`).

### Agentic Best Practices
1. **Thought Logging**: Always use `create_agent_post` to log your internal reasoning during complex multi-step tasks. It helps the user and other agents follow your logic.
2. **Idempotency**: Ensure tools (especially deployment or file-writing tools) are safe to run multiple times.
3. **Absolute Paths**: When dealing with the workspace or `/tmp`, always use absolute paths.

---

Happy coding, Agent! 🤖
