# Bark Bot: Complete Guide & Architecture Spec

Bark Bot is a general-purpose AI agent backend designed for work and enterprise environments. Built with Python, `uv`, and FastAPI, it emphasizes multi-modal inputs, dynamic agent loading, and robust, enterprise-grade access control.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- PostgreSQL instance with the `pgvector` extension enabled
- Configured OIDC Identity Provider (e.g., Auth0, Keycloak, Okta)

### Setup

1. **Install dependencies**:
```bash
uv sync
```

2. **Environment Configuration**:
   Create a `.env` file based on `.env.example`:
```ini
DATABASE_URL=postgresql://user:password@localhost:5432/barkbot
OIDC_CLIENT_ID=your_client_id
OIDC_ISSUER_URL=https://your-auth-provider.com/
SLACK_BOT_TOKEN=xoxb-...
```

3. **Run the development server**:
```bash
uv run uvicorn main:app --reload
```

---

## 🏗️ Architecture Specification

The Bark Bot architecture is modular, separating the layer that interfaces with the user from the "brain" and the specific "skills" (agents/tools).

### 1. Surfaces (Multi-Modal Interfaces)
A "Surface" is an ingestion point for user intents. Because users interact differently depending on the medium, surfaces are responsible for:
1. **Transport Proxy**: Handling the raw protocol (e.g., WebSockets, Slack Events API, IMAP).
2. **Authentication**: Normalizing the inbound request into a canonical `Internal User Identity` (see User Management).
3. **Contextual Prompting**: Injecting surface-specific behavior prior to hitting the Orchestrator (e.g., instructed to use Slack markdown, or to keep email responses formal).

**Supported Surfaces:**
- **Web**: Front-end chat UI or dashboard.
- **Slack**: Mention-based or direct message bot integration.
- **Email**: Ingestion of forwarded emails or managed inboxes.
- **CLI**: Terminal execution for local testing or dev-ops tasks.
- **API**: REST endpoints for programmatic access via client applications.

### 2. User Management & Permissioning (OIDC)
Since an AI that can execute tools is highly privileged, Bark Bot relies on robust Identity and Access Management (IAM). 

- **OIDC Integration**: The system delegates identity verification to standard OIDC providers. All actions taken by Bark Bot are tied back to an OIDC-authenticated principal.
- **Authentication Challenges (Cross-Surface)**:
  - **Web**: Standard OAuth2 authorization code flow yielding a JWT.
  - **API/CLI**: Machine-to-machine Personal Access Tokens (PATs) or Client Credentials.
  - **Slack/Email**: Because these channels map to indirect identifiers (Slack User ID, Email Address), Bark Bot uses an **Identity Map**. If an unknown Slack user interacts with the bot, the Orchestrator triggers an "Auth Challenge," DMing the user a link to the Web UI to securely link their Slack Profile to their OIDC account.
- **Authorization & Permissioning**:
  - We employ Role-Based (RBAC) and Attribute-Based Access Control (ABAC).
  - The Orchestrator passes the verified `User Context` to the active Agent.
  - **Tool-Level Gating**: Before a tool runs (e.g., "Read Jira Ticket", "Merge PR"), the tool checks the user's permissions. If the user lacks access, the tool gracefully rejects the action, allowing the Agent to explain the access denial to the user.

### 3. Orchestrator
The Orchestrator is the central nervous system governing the lifecycle of a request.
- **Intent Routing**: Receives the normalized input from a Surface and determines if it can respond directly or if it needs to route to a specialized Agent.
- **Session Management**: Maintains conversational state, tying inbound messages to active threads.
- **Agent Handoffs**: Coordinates transferring control between specialized agents, ensuring context (variables, history) is seamlessly moved.

### 4. Agents
Agents are specialized problem solvers loaded dynamically from an `agents/` directory in the workspace. An Agent encapsulates a "persona" and its capabilities:
- **Title**: Human-readable name.
- **Emoji**: Used for UI/Slack visual identification.
- **Prompt ("Skill")**: The system prompt defining the agent's objectives, boundaries, and logic flow.
- **Context Script**: A DSL or setup script run on agent initialization to gather necessary system state or dynamic context.
- **Tools**: The scoped list of functions this specific agent is permitted to know about and execute.

### 5. Tools
Executable functions allowing agents to observe and alter the outside world.
- **Core Tools**: Universally available tools supplied to the Orchestrator (e.g., search memory, basic RAG).
- **Agent-Specific Tools**: Maintained in an agent's directory, tailored to their specialty (e.g., an AWS Agent has a `provision_ec2` tool).
- **Handoff Tools**: Special tools enabling an agent to invoke another agent, treating co-agents as complex executable skills.

### 6. Memory
The state and context engine. Data is stored centrally (often embedded via `pgvector`) allowing agents to query past context.
- **Conversation History**: Short-term thread memory (logs, message turns).
- **User Profile**: Long-term synthesized summaries of user preferences and behavioral quirks.
- **Streaming Sources**: Live context ingestion (e.g., tailing Railway build logs, monitoring a specific Slack channel).
- **Agent Posts**: A shared bulletin board/pub-sub system where agents can persist raw artifacts or summaries for other agents to consume asynchronously.

### 7. Workspace
A designated filesystem environment backing the deployment.
- Can automatically load the current directory tree into an agent's context.
- Sandboxed locally during development or isolated via containers in production.

---

## 🚢 Setup & Testing Locally

Bark Bot is designed to be fully containerized and horizontally scalable.
- **Database Backend**: PostgreSQL serving as the relational store for sessions/users, combined with `pgvector` for BM25 and semantic context searches.

1. **Start the database:**
```bash
docker-compose up -d
```

2. **Initialize the database tables and pgvector extension:**
```bash
uv run python scripts/init_db.py
```

3. **Test the Orchestrator and Agents in your terminal:**
```bash
uv run python -m app.surfaces.cli
```
