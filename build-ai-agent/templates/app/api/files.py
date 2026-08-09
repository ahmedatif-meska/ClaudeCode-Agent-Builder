"""Knowledge-base file management. RAG builds only — delete this router otherwise."""

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.schemas import DeleteResponse, FileListResponse, FileRecord
from app.openai_client import get_openai_client
from app.rag.files import (
    FileValidationError,
    delete_file,
    list_files,
    upload_file,
)
from app.rag.vector_store import get_vector_store_id

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=FileListResponse)
async def get_files() -> FileListResponse:
    files = await list_files(get_openai_client(), get_vector_store_id())
    return FileListResponse(files=files)


@router.post("", response_model=FileRecord, status_code=201)
async def post_file(file: UploadFile) -> FileRecord:
    content = await file.read()
    try:
        return await upload_file(
            get_openai_client(),
            get_vector_store_id(),
            file.filename or "upload",
            content,
        )
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{file_id}", response_model=DeleteResponse)
async def remove_file(file_id: str) -> DeleteResponse:
    deleted = await delete_file(get_openai_client(), get_vector_store_id(), file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found in the knowledge base.")
    return DeleteResponse(id=file_id, deleted=True)
