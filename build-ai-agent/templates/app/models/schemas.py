"""Request/response models. Keep these free of any secret or provider-internal field."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)
    # Server-side conversation id. Omit on the first turn; send back what the server
    # returned to continue the same conversation.
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    agent: str
    capabilities: list[str]


# --- RAG only (delete if File Search was not confirmed) ---


class FileRecord(BaseModel):
    id: str
    filename: str | None = None
    status: Literal["in_progress", "completed", "failed", "cancelled"]
    bytes: int | None = None
    error: str | None = None


class FileListResponse(BaseModel):
    files: list[FileRecord]


class DeleteResponse(BaseModel):
    id: str
    deleted: bool
