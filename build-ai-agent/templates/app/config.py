"""Application settings. All secrets stay server-side — never returned by any endpoint."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str

    # None => let the Agents SDK pick its current default model.
    agent_model: str | None = None
    agent_name: str = "Assistant"
    agent_instructions: str = (
        "You are a helpful assistant. Answer accurately and concisely. "
        "If you do not know something, say so rather than guessing."
    )
    # Hard cap on agent loop iterations. Prevents a tool-calling loop from hanging a request.
    max_turns: int = 10

    cors_origins: list[str] = ["http://localhost:3000"]

    # RAG: set once by scripts/create_vector_store.py. Omit the whole RAG module if
    # File Search was not confirmed.
    vector_store_id: str | None = None

    # MCP: only present if an MCP server was confirmed AND verified.
    mcp_server_url: str | None = None
    mcp_server_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process."""
    return Settings()  # type: ignore[call-arg]  # values come from env/.env
