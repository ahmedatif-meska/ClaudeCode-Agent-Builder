"""Health + capability report. Never returns a key, token, or connection string."""

from fastapi import APIRouter, Request

from app.agents.factory import agent_capabilities
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    agent = request.app.state.agent
    return HealthResponse(
        status="ok",
        agent=agent.name,
        # Shows which tools/MCP servers actually loaded — the fastest way to catch a
        # capability that silently failed to configure.
        capabilities=agent_capabilities(agent),
    )
