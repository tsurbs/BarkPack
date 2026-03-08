# BarkPack Coding Agent — Vision Statement
> Internal strategy document. For agents contributing to this codebase.
> Understand this before working on the coding_agent skill or any sandbox_* tooling.

---

## What this agent is

The coding agent is not a code completion widget. It is a junior engineer that can be handed a task, given access to a codebase, and trusted to return with working, tested, committed code — or a clear explanation of why it could not. It operates end-to-end: from a plain-English description or a GitHub issue URL, through cloning, reading, implementing, testing, diffing, committing, and opening a pull request, without a human in the loop unless one is wanted.

The agent runs as a native BarkPack skill. It uses the `sandbox_*` tool family backed by the Daytona SDK. OpenCode informed the design of its tools and system prompt, but is not a runtime dependency. There is no subprocess, no nested agent loop, no black box. Every file read, bash command, and git operation is a first-class BarkPack tool call, visible in the session database, subject to `check_permissions`.

---

## Current capabilities

**End-to-end task execution.** Clone a repo, read the relevant code, implement the change, run tests, review the diff, commit with a conventional message, open a PR. The full chain from issue to PR without required human intervention.

**Sandboxed isolation.** Every task runs in its own Daytona container. The agent cannot affect the host machine, leak credentials, or touch production. Sandbox isolation is architectural, not policy.

**Full observability.** Because the coding agent is a native BarkPack skill using native tools, every operation is a session DB event. There is no secondary log. Users and other agents see exactly what happened.

**Permission-gated operations.** Destructive operations (pushing to protected branches, `rm -rf`, deployment) are blocked by structural guardrails before they reach Daytona. The `check_permissions` system gives teams fine-grained autonomy control.

**Codebase memory and deduplication.** The `coding_tasks` table with pgvector embeddings stores every task ever executed. Before starting new work, the agent searches for similar prior tasks. If the same class of bug was fixed six months ago in a different service, the agent finds it and can reference the prior commit or approach.

**Parallel subagent delegation.** Complex tasks can spawn parallel subagents via `load_skill` — one researching the codebase, another writing tests, another implementing. Results flow back to the parent. Depth limit and task budget prevent runaway delegation.

**Demonstrated output via screen recording.** After implementing a feature, the agent can start the application in a Daytona virtual desktop, record a demonstration, and return the video as a `__ATTACHMENT__`. The user sees the feature running before reviewing a single line of code.

---

## Honest limitations

These are not bugs to be fixed. They are properties of the current state of AI that any agent working on this system must understand.

**Long-horizon planning.** The agent handles well-scoped tasks with clear success criteria. It struggles with open-ended architectural decisions where the right answer requires understanding years of accumulated context, technical debt, and organizational constraints that no context window fully holds.

**Novel bug diagnosis.** Bugs with clear reproduction steps: reliable. Heisenbugs, race conditions, and failures that only appear under specific load patterns: unreliable. The agent lacks the intuition a seasoned engineer develops from years of production debugging.

**Code taste.** The agent knows what is correct. It does not always know what is elegant. It produces working code that a senior engineer might refactor — not because it is wrong, but because it lacks the aesthetic sense that distinguishes a clean codebase from a merely functional one.

**Cross-repository reasoning.** Today one task maps to one repository. Many real engineering problems span multiple services, shared libraries, and infrastructure configs. The agent cannot yet reason about how a change in service A affects service B's contract.

**Security intuition.** The agent can run linters and known-vulnerability scanners. It cannot reason about novel attack surfaces — the kind of security flaw that emerges from a subtle interaction between two correct-looking decisions. Human security review remains mandatory for anything customer-facing.

**Recovery from badly-scoped tasks.** Given an ambiguous task, the agent makes assumptions and proceeds. Those assumptions are usually reasonable. When they are wrong, the agent can dig into a hole that requires a human to recognize and correct. Scoping tasks tightly before invocation is the primary mitigation.

---

## Strategic position

### The moat is not the model

Every AI coding tool races to improve its LLM. That race is expensive, commoditizing, and ultimately won by whoever has the largest compute budget. The coding agent does not compete on that axis. The LLM is a replaceable component — swap Claude for GPT-5 or Gemini by changing a config line. The moat is the infrastructure: sandbox isolation, observability, the permission system, the organizational memory in pgvector. These are hard to copy and compound over time.

### The bulletin board is an unfair advantage

Most coding agents are stateless. BarkPack's coding agent writes to the `agent_posts` bulletin board, which is read by every other agent in the system. Over time the system accumulates a structured memory of every architectural decision, every bug fix, every refactor. The coding agent gets smarter not because the model improves, but because the organization's knowledge becomes machine-readable. This moat widens with every task executed.

### The multi-agent ecosystem is the product

A standalone coding agent is a productivity tool. A coding agent embedded in an ecosystem alongside a marketing agent, data agent, support agent, and planning agent is something categorically different — a nervous system for a software company. When the support agent identifies a recurring bug pattern, it briefs the coding agent directly. When the planning agent breaks a feature into tasks, the coding agent executes them in parallel. The value of each agent multiplies the value of every other.

---

## The horizon

These are not speculative features. Each is a direct extension of the architecture already built. The question is sequencing, not possibility.

**Cross-repository awareness (now → Q2 2025).** The `sandbox_create` tool today clones one repo. Extending it to clone multiple repos into the same sandbox — API, client SDK, infrastructure config — unlocks the most common class of real engineering task: the coordinated multi-service change. The architecture supports this; it requires only expanded tooling and a richer task schema.

**Proactive maintenance agent (Q3 2025).** Rather than waiting for tasks, the agent monitors repositories for dependency vulnerabilities, deprecated API usage, test coverage regressions, and bundle size growth. It opens PRs autonomously for safe fixes and surfaces alerts for anything requiring judgment. The engineering team wakes up to a cleaner codebase every morning.

**LSP-powered diagnosis (Q3 2025).** Running a language server inside the Daytona sandbox and injecting live type errors and lint warnings into the agent's context each turn closes the feedback loop on code quality. Today the agent learns about errors when tests run. With LSP integration it learns as it writes — the same feedback loop a human engineer has in their IDE.

**Specification-first development (Q4 2025).** The planning agent writes a specification. The coding agent turns it into a test suite. The test suite becomes the definition of done. Implementation begins only when the contract is clear and machine-verifiable. This inverts the current workflow — tests first, code second — and produces more reliable output because the agent has an unambiguous success criterion from the first token.

**Institutional code knowledge (2026).** The pgvector embeddings in `coding_tasks` today store task descriptions. The natural extension is to embed the codebase itself — functions, modules, architectural patterns — and keep those embeddings current as the code changes. The agent stops reading the codebase from scratch on every task. It retrieves relevant context, understands the conventions, and works in the style of the team. The codebase becomes a knowledge base.

**The on-call agent (2026).** When a production alert fires, BarkPack's monitoring agent pages the coding agent. The coding agent opens the logs in a sandbox, traces the error, identifies the likely cause, prepares a fix and a rollback plan, and presents both to the on-call engineer within minutes. The engineer approves. The fix ships. The post-mortem writes itself. This is not science fiction — it is the current architecture applied to a new event source.

---

## The core bet

Software companies spend the majority of their engineering time not on new features, but on maintenance, debugging, dependency management, and the quiet accumulation of technical debt. These tasks are high-cost, low-prestige, and deeply amenable to automation. The team that automates them first does not just move faster — it compounds. Every hour reclaimed from maintenance is an hour invested in the work that actually differentiates the product.

The coding agent is a bet that this compounding is real, large, and available now.

---

## What success looks like

In two years, a BarkPack user should be able to describe a feature in plain language on a Monday morning, have a pull request open by Monday afternoon, and spend the rest of the week on decisions that require human judgment: what to build next, how to talk to customers, where the architecture needs to go. The coding agent handles implementation. The human handles vision.

That division of labor is technically achievable with the infrastructure already built. The work now is execution.

---

## Implications for agents working on this codebase

If you are an agent contributing to the `coding_agent` skill or the `sandbox_*` tools:

- Preserve the native BarkPack tool architecture. Do not reintroduce a subprocess model or a secondary agent loop. Every operation must be observable in the BarkPack session DB.
- Treat `check_permissions` as mandatory on every tool that writes, executes, or pushes. It is the only thing standing between the agent and a destructive operation in a real codebase.
- When adding new capabilities, ask whether they belong as a new `sandbox_*` tool (a discrete, observable, permission-gated operation) or as skill-level logic in `coding_agent.yaml`. Prefer tools — they are reusable by other skills and other agents.
- Write to `coding_tasks` on every state change. The DB is the ground truth for task history, cost accounting, and semantic deduplication. An operation that is not recorded did not happen as far as the rest of the system is concerned.
- Use `create_agent_post` to log reasoning, dead ends, and architectural decisions. The bulletin board is the memory of the system. Future agents — and future versions of the coding agent itself — will read what you write here.

The goal is not an agent that can code. The goal is an agent that understands your software — its history, its conventions, its fragile parts, its ambitions — and works on it the way a trusted engineer would.