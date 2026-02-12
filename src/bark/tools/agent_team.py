"""Bark Agent Team — 10 additional specialist agents.

Combined with the 5 existing agents (writing_agent, knowledge_agent,
data_agent, fullstack_agent, code_edit_agent), these form Bark's
15-agent team.

Agent Roster:
 1. writing_agent      (existing - specialist_tools.py)
 2. knowledge_agent    (existing - specialist_tools.py)
 3. data_agent         (existing - code_tools.py)
 4. fullstack_agent    (existing - frontend_tools.py)
 5. code_edit_agent    (existing - claude_code_tools.py)
 6. research_agent     <- NEW (deep web research)
 7. planner_agent      <- NEW (task decomposition)
 8. review_agent       <- NEW (code/content review)
 9. comms_agent        <- NEW (draft emails/messages)
10. analytics_agent    <- NEW (metrics & reporting)
11. design_agent       <- NEW (UI/UX guidance)
12. security_agent     <- NEW (security review)
13. docs_agent         <- NEW (documentation)
14. debug_agent        <- NEW (debugging & diagnostics)
15. onboarding_agent   <- NEW (new member help)
"""

import logging
import time
from typing import Any

import httpx

from bark.core.config import get_settings
from bark.core.tools import tool

logger = logging.getLogger(__name__)

SPECIALIST_TIMEOUT = 180


async def _run_agent(
    task: str,
    context: str,
    model: str,
    system_prompt: str,
) -> str:
    """Run a specialist agent via OpenRouter. Single-shot (no tools)."""
    settings = get_settings()
    parts = []
    if context:
        parts.append(f"## Conversation Context\n\n{context}")
    parts.append(f"## Task\n\n{task}")
    user_content = "\n\n---\n\n".join(parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        timeout=SPECIALIST_TIMEOUT,
    ) as client:
        start = time.time()
        logger.info(f"[Agent] Calling {model}")
        resp = await client.post("/chat/completions", json={
            "model": model,
            "messages": messages,
        })
        logger.info(f"[Agent] {model} responded in {time.time()-start:.2f}s")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"].get("content", "(no content)")


# ═══════════════════════════════════════════════════════════════════
# AGENT 6: Research Agent
# Deep web research using Firecrawl + synthesis
# ═══════════════════════════════════════════════════════════════════

RESEARCH_SYSTEM_PROMPT = """You are a specialist research agent for ScottyLabs.
You excel at:
- Deep research and investigation on any topic
- Synthesizing information from multiple sources into clear summaries
- Comparing alternatives and making evidence-based recommendations
- Finding specific technical information, documentation, and best practices
- Competitive analysis and market research

Produce thorough, well-organized research briefs with clear sections,
key findings, and actionable recommendations. Cite your reasoning."""


@tool(
    name="research_agent",
    description=(
        "Delegate a deep research task to a specialist research model. "
        "Use for investigating topics, comparing technologies, market research, "
        "finding best practices, or any task requiring thorough analysis. "
        "Returns a structured research brief.\n\n"
        "IMPORTANT: Provide conversation context so the specialist understands the situation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The research question or investigation task."},
            "context": {"type": "string", "description": "Conversation context and background."},
        },
        "required": ["task"],
    },
)
async def research_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.knowledge_model, RESEARCH_SYSTEM_PROMPT)
        return f"**Research Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Research agent failed")
        return f"❌ Research agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 7: Planner Agent
# Task decomposition, project planning, sprint planning
# ═══════════════════════════════════════════════════════════════════

PLANNER_SYSTEM_PROMPT = """You are a specialist project planning agent for ScottyLabs.
You excel at:
- Breaking down complex projects into actionable tasks
- Creating timelines and milestones
- Identifying dependencies between tasks
- Sprint planning and backlog grooming
- Resource allocation and workload balancing
- Risk identification and mitigation planning

Output structured plans with numbered tasks, owners (if known),
time estimates, dependencies, and priority levels.
Use markdown tables for timelines when appropriate."""


@tool(
    name="planner_agent",
    description=(
        "Delegate a planning or task decomposition request to a specialist planner. "
        "Use for breaking down projects, creating timelines, sprint planning, "
        "identifying dependencies, or organizing complex work.\n\n"
        "IMPORTANT: Provide conversation context so the planner understands the full scope."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The project or task to plan/decompose."},
            "context": {"type": "string", "description": "Conversation context, constraints, and background."},
        },
        "required": ["task"],
    },
)
async def planner_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.knowledge_model, PLANNER_SYSTEM_PROMPT)
        return f"**Planner Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Planner agent failed")
        return f"❌ Planner agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 8: Review Agent
# Code review, content review, quality assurance
# ═══════════════════════════════════════════════════════════════════

REVIEW_SYSTEM_PROMPT = """You are a specialist code and content review agent for ScottyLabs.
You excel at:
- Reviewing code for bugs, performance issues, and best practices
- Reviewing documents, proposals, and communications for clarity and accuracy
- Identifying potential security vulnerabilities in code
- Suggesting improvements with specific, actionable feedback
- Checking for consistency with established patterns and conventions

Structure your review with:
1. Overall assessment (pass/needs changes/reject)
2. Critical issues (must fix)
3. Suggestions (nice to have)
4. Positive observations (what's good)

Be constructive and specific. Reference line numbers when reviewing code."""


@tool(
    name="review_agent",
    description=(
        "Delegate a review task to a specialist reviewer. "
        "Use for code reviews, document reviews, proposal feedback, "
        "or quality assurance checks. Provides structured feedback.\n\n"
        "IMPORTANT: Include the content to review in the task or context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to review and what to focus on."},
            "context": {"type": "string", "description": "The content to review, plus conversation context."},
        },
        "required": ["task"],
    },
)
async def review_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.code_model, REVIEW_SYSTEM_PROMPT)
        return f"**Review Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Review agent failed")
        return f"❌ Review agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 9: Comms Agent
# Email drafting, Slack messages, meeting agendas, announcements
# ═══════════════════════════════════════════════════════════════════

COMMS_SYSTEM_PROMPT = """You are a specialist communications agent for ScottyLabs.
You excel at:
- Drafting professional emails and Slack messages
- Writing meeting agendas and minutes
- Creating announcements and newsletters
- Crafting outreach messages to sponsors, partners, and students
- Adapting tone for different audiences (formal sponsors, casual students, internal team)
- Writing event descriptions and promotional copy

ScottyLabs is a student organization at Carnegie Mellon University that builds
technology for the campus community. Key events include TartanHacks (hackathon),
ScottyLabs educational programs, and various tech projects.

Match the tone to the audience. Be concise for Slack, professional for emails,
engaging for announcements."""


@tool(
    name="comms_agent",
    description=(
        "Delegate a communications task to a specialist comms agent. "
        "Use for drafting emails, Slack messages, announcements, meeting agendas, "
        "outreach messages, or any written communication.\n\n"
        "IMPORTANT: Specify the audience, tone, and purpose."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to write — specify audience, tone, and purpose."},
            "context": {"type": "string", "description": "Conversation context and any relevant details."},
        },
        "required": ["task"],
    },
)
async def comms_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.writing_model, COMMS_SYSTEM_PROMPT)
        return f"**Comms Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Comms agent failed")
        return f"❌ Comms agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 10: Analytics Agent
# Data analysis, metrics, KPI tracking, visualization specs
# ═══════════════════════════════════════════════════════════════════

ANALYTICS_SYSTEM_PROMPT = """You are a specialist analytics agent for ScottyLabs.
You excel at:
- Analyzing event attendance data, survey results, and engagement metrics
- Creating KPI dashboards and tracking frameworks
- Statistical analysis and trend identification
- Interpreting Google Analytics, Slack analytics, and social media metrics
- Budget analysis and financial projections
- Designing data collection strategies

Output clear analyses with:
- Key metrics and their trends
- Notable patterns or anomalies
- Actionable insights
- Recommendations based on data

Use tables for data comparisons. Be specific with numbers."""


@tool(
    name="analytics_agent",
    description=(
        "Delegate a data analysis or metrics task to a specialist analytics agent. "
        "Use for analyzing event data, survey results, KPIs, budget analysis, "
        "engagement metrics, or creating tracking frameworks.\n\n"
        "IMPORTANT: Provide the data or context about what data is available."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The analysis task — what to analyze and what insights to produce."},
            "context": {"type": "string", "description": "Available data, metrics, or context."},
        },
        "required": ["task"],
    },
)
async def analytics_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.knowledge_model, ANALYTICS_SYSTEM_PROMPT)
        return f"**Analytics Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Analytics agent failed")
        return f"❌ Analytics agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 11: Design Agent
# UI/UX guidance, design system, branding
# ═══════════════════════════════════════════════════════════════════

DESIGN_SYSTEM_PROMPT = """You are a specialist design agent for ScottyLabs.
You are an expert in:
- The ScottyLabs Design System (Satoshi + Inter fonts, scotty-red brand colors, Tailwind CSS, even-number spacing)
- UI/UX design principles and best practices
- Responsive web design and accessibility (WCAG)
- Component design and design tokens
- Information architecture and user flows
- Design critiques and feedback

ScottyLabs brand:
- Primary: scotty-red (#C41230)
- Fonts: Satoshi (headings), Inter (body)
- Spacing: even-number scale (4, 8, 12, 16, 24, 32, 48, 64)
- Style: Clean, modern, student-friendly

Provide specific, implementable design guidance with:
- Color values, spacing, typography specs
- Component structure recommendations
- Accessibility considerations
- Mobile-first responsive breakpoints"""


@tool(
    name="design_agent",
    description=(
        "Delegate a design task to a specialist UI/UX agent. "
        "Use for design system questions, UI component design, "
        "layout guidance, accessibility review, or branding decisions. "
        "Knows the ScottyLabs Design System.\n\n"
        "IMPORTANT: Describe what you're designing and for which platform."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The design task or question."},
            "context": {"type": "string", "description": "Context about the project and existing design."},
        },
        "required": ["task"],
    },
)
async def design_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.frontend_model, DESIGN_SYSTEM_PROMPT)
        return f"**Design Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Design agent failed")
        return f"❌ Design agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 12: Security Agent
# Security review, vulnerability analysis, best practices
# ═══════════════════════════════════════════════════════════════════

SECURITY_SYSTEM_PROMPT = """You are a specialist security agent for ScottyLabs.
You excel at:
- Reviewing code for security vulnerabilities (OWASP Top 10)
- API security best practices (auth, rate limiting, input validation)
- Secret management and environment variable handling
- Dependency vulnerability assessment
- Access control and permission design
- Security incident response planning
- OAuth2, JWT, and authentication flows

Focus on practical, actionable security advice:
1. Critical vulnerabilities (must fix immediately)
2. High-risk issues (fix soon)
3. Best practice improvements (nice to have)
4. Positive security patterns (what's done well)

Always explain WHY something is a vulnerability and HOW to fix it."""


@tool(
    name="security_agent",
    description=(
        "Delegate a security review or question to a specialist security agent. "
        "Use for code security reviews, vulnerability assessment, auth design, "
        "secret management advice, or security best practices.\n\n"
        "IMPORTANT: Include relevant code or configuration in the context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The security task — what to review or advise on."},
            "context": {"type": "string", "description": "Code, configuration, or context to review."},
        },
        "required": ["task"],
    },
)
async def security_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.code_model, SECURITY_SYSTEM_PROMPT)
        return f"**Security Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Security agent failed")
        return f"❌ Security agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 13: Docs Agent
# Documentation generation, wiki updates, README writing
# ═══════════════════════════════════════════════════════════════════

DOCS_SYSTEM_PROMPT = """You are a specialist documentation agent for ScottyLabs.
You excel at:
- Writing clear, comprehensive technical documentation
- Creating API documentation and usage guides
- Writing README files and getting-started guides
- Generating wiki articles and knowledge base entries
- Creating onboarding docs and runbooks
- Documenting architecture decisions (ADRs)
- Writing changelogs and release notes

Follow these documentation principles:
- Start with WHY, then WHAT, then HOW
- Include code examples for technical docs
- Use headers, tables, and code blocks for structure
- Write for the audience (new member vs. experienced dev)
- Keep it concise but complete"""


@tool(
    name="docs_agent",
    description=(
        "Delegate a documentation task to a specialist docs agent. "
        "Use for writing README files, API docs, wiki articles, "
        "onboarding guides, runbooks, changelogs, or architecture docs.\n\n"
        "IMPORTANT: Specify the audience and what needs documenting."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to document and for whom."},
            "context": {"type": "string", "description": "Source material, code, or context to document."},
        },
        "required": ["task"],
    },
)
async def docs_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.writing_model, DOCS_SYSTEM_PROMPT)
        return f"**Docs Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Docs agent failed")
        return f"❌ Docs agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 14: Debug Agent
# Debugging, diagnostics, error analysis
# ═══════════════════════════════════════════════════════════════════

DEBUG_SYSTEM_PROMPT = """You are a specialist debugging agent for ScottyLabs.
You excel at:
- Analyzing error messages, stack traces, and logs
- Identifying root causes of bugs
- Debugging Python async/await issues
- Diagnosing API integration problems (Slack, Google, OpenRouter)
- Troubleshooting deployment issues (Docker, Railway)
- Performance profiling and bottleneck identification
- Memory leak detection

Debugging methodology:
1. Reproduce: Understand the exact conditions
2. Isolate: Narrow down the component
3. Identify: Find the root cause (not just symptoms)
4. Fix: Propose specific code changes
5. Verify: Suggest how to confirm the fix

Always provide specific, testable solutions. Include code snippets for fixes."""


@tool(
    name="debug_agent",
    description=(
        "Delegate a debugging or diagnostics task to a specialist debug agent. "
        "Use for analyzing errors, stack traces, logs, performance issues, "
        "or any troubleshooting task.\n\n"
        "IMPORTANT: Include error messages, stack traces, or logs in the context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The bug or issue to diagnose."},
            "context": {"type": "string", "description": "Error messages, stack traces, logs, and relevant code."},
        },
        "required": ["task"],
    },
)
async def debug_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.code_model, DEBUG_SYSTEM_PROMPT)
        return f"**Debug Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Debug agent failed")
        return f"❌ Debug agent error: {e}"


# ═══════════════════════════════════════════════════════════════════
# AGENT 15: Onboarding Agent
# New member help, ScottyLabs orientation, FAQ
# ═══════════════════════════════════════════════════════════════════

ONBOARDING_SYSTEM_PROMPT = """You are a specialist onboarding agent for ScottyLabs.
You are the friendly guide for new members joining ScottyLabs at Carnegie Mellon University.

You know about:
- ScottyLabs committees: Tech, Labrador, Design, Events, Outreach, Finance, Foundry, Admin
- Key projects: Bark (AI assistant), TartanHacks (hackathon), CMU Courses, Print@CMU
- Tools: Slack (primary communication), Notion (docs), Google Workspace, GitHub
- Meeting cadence and how decisions are made
- How to get access to tools and repositories
- Common first tasks for new members

Your tone is warm, encouraging, and patient. Remember that new members may be
nervous or unfamiliar with the tech stack. Answer questions thoroughly and
suggest next steps proactively.

If you don't know something specific, say so and suggest who to ask or where to look."""


@tool(
    name="onboarding_agent",
    description=(
        "Delegate an onboarding question to a specialist agent that helps "
        "new ScottyLabs members. Use for orientation questions, getting started, "
        "understanding committees, finding resources, or any new-member FAQ.\n\n"
        "Great for questions like 'how do I join tech committee?' or "
        "'what should I work on first?'"
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The question or onboarding topic."},
            "context": {"type": "string", "description": "Context about the new member and their interests."},
        },
        "required": ["task"],
    },
)
async def onboarding_agent(task: str, context: str = "") -> str:
    try:
        settings = get_settings()
        result = await _run_agent(task, context, settings.writing_model, ONBOARDING_SYSTEM_PROMPT)
        return f"**Onboarding Agent Result:**\n\n{result}"
    except Exception as e:
        logger.exception("Onboarding agent failed")
        return f"❌ Onboarding agent error: {e}"
