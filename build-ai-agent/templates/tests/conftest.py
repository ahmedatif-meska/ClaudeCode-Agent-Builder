"""Test setup: fake credentials, no network, no tracing exports."""

import os

os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')

from agents import set_tracing_disabled  # noqa: E402

# Without this the SDK tries to POST traces to OpenAI during tests.
set_tracing_disabled(True)
