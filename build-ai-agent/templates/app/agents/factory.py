"""Composes the agent from the capabilities that were actually confirmed.

Every block below is conditional on purpose: an agent with tools it does not need is
slower, more expensive, and more likely to take a wrong turn. Delete the blocks for
capabilities this build does not have rather than leaving them switched off.
"""

from agents import Agent, FileSearchTool, Tool
from agents.mcp import MCPServer

from app.agents.tools import CUSTOM_TOOLS
from app.config import get_settings


def build_agent(mcp_servers: list[MCPServer] | None = None) -> Agent:
    settings = get_settings()
    tools: list[Tool] = []

    # --- RAG (only when File Search was confirmed and a vector store exists) ---
    if settings.vector_store_id:
        tools.append(
            FileSearchTool(
                vector_store_ids=[settings.vector_store_id],
                max_num_results=8,
            )
        )

    # --- Custom function tools (empty list if none were needed) ---
    tools.extend(CUSTOM_TOOLS)

    return Agent(
        name=settings.agent_name,
        instructions=_instructions(settings.agent_instructions, bool(tools)),
        model=settings.agent_model,  # None => Agents SDK default model
        tools=tools,
        mcp_servers=mcp_servers or [],
    )


def _instructions(base: str, has_tools: bool) -> str:
    if not has_tools:
        return base
    # Without this, agents re-search the same thing every turn and requests take
    # tens of seconds instead of a few.
    return (
        f"{base}\n\n"
        "Use your tools when they are needed to answer accurately. Do not call the same "
        "tool with the same arguments twice in one turn — reuse the result you already have. "
        "If the tools return nothing relevant, say so instead of inventing an answer."
    )


def agent_capabilities(agent: Agent) -> list[str]:
    """Human-readable capability list for /health — useful for confirming what actually loaded."""
    names: list[str] = []
    for tool in agent.tools:
        names.append(getattr(tool, "name", type(tool).__name__))
    names.extend(f"mcp:{server.name}" for server in agent.mcp_servers)
    return names
