"""FastAPI entrypoint.

Run: uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.factory import build_agent
from app.api import chat, health
from app.config import get_settings
from app.openai_client import get_openai_client

# RAG only:
# from app.api import files
# MCP only:
# from app.mcp_servers.connection import connect_mcp_servers, disconnect_mcp_servers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    get_openai_client()  # fail fast on a missing/blank key, and register it for tracing

    # MCP servers must be connected before the agent is built, and cleaned up from
    # this same task — their sessions use task-scoped cancel scopes.
    # app.state.mcp_servers = await connect_mcp_servers(settings)
    app.state.mcp_servers = []

    app.state.agent = build_agent(mcp_servers=app.state.mcp_servers)
    try:
        yield
    finally:
        # await disconnect_mcp_servers(app.state.mcp_servers)
        pass


app = FastAPI(title="Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
# app.include_router(files.router)  # RAG only
