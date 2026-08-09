"""Single shared AsyncOpenAI client.

One client per process: it owns an httpx connection pool, so creating one per request
leaks sockets and adds TLS handshakes to every call.
"""

from functools import lru_cache

from agents import set_default_openai_client
from openai import AsyncOpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    # Make the Agents SDK (model calls + tracing) use this same client/key.
    set_default_openai_client(client, use_for_tracing=True)
    return client
