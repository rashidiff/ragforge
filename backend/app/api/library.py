"""Managed Library uploads, mutations, status, and exact-source PDF preview."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.domain.schemas import DeletionAccepted, DocumentList, IndexJob, SourceDetail, UploadAccepted

from app.services.pdf_ingestion import LibraryStore, managed_pdf_path, validate_upload

router = APIRouter(prefix="/api/library", tags=["library"])


def library(request: Request) -> LibraryStore:
    return request.app.state.runtime.index.library


@router.get("", response_model=DocumentList)
def list_documents(request: Request):
    return {"documents": [document for document in library(request).list()
                          if document["status"] not in {"deleted", "deleting"}]}


@router.post("/upload", response_model=UploadAccepted, status_code=202)
async def upload_pdf(file: UploadFile, request: Request):
    runtime = request.app.state.runtime
    validated = None
    try:
        runtime.activity.emit("upload_validating", filename=file.filename)
        validated = await validate_upload(file, runtime.index.library.directory, runtime.settings.max_upload_bytes)
        accepted = await run_in_threadpool(runtime.index.submit, "upload", None, validated)
        return {"document": accepted["document"], "job_id": accepted["job"]["job_id"]}
    finally:
        if validated is not None:
            validated.discard()
        await file.close()


@router.delete("/{document_id}", response_model=DeletionAccepted, status_code=202)
def delete_document(document_id: UUID, request: Request):
    try:
        accepted = request.app.state.runtime.index.submit("delete", str(document_id))
    except KeyError as exc:
        raise HTTPException(404) from exc
    return {"job_id": accepted["job"]["job_id"], "status": "deleting"}


@router.post("/{document_id}/reindex", response_model=IndexJob, status_code=202)
def reindex_document(document_id: UUID, request: Request):
    try:
        return request.app.state.runtime.index.submit("reindex", str(document_id))["job"]
    except KeyError as exc:
        raise HTTPException(404) from exc


@router.get("/{document_id}/pdf", response_class=FileResponse)
def preview(document_id: UUID, request: Request):
    store = library(request)
    document = next((entry for entry in store.list()
                     if entry["document_id"] == str(document_id)
                     and entry["status"] not in {"deleted", "deleting"}), None)
    if document is None:
        raise HTTPException(404)
    path = managed_pdf_path(store.directory, str(document_id))
    if not path.is_file():
        raise HTTPException(404)
    # The caller uses #page=N; arbitrary filesystem paths are never accepted.
    return FileResponse(path, media_type="application/pdf", filename=document["original_name"],
                        content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/{document_id}/sources/{chunk_id}", response_model=SourceDetail)
def source_excerpt(document_id: UUID, chunk_id: UUID, request: Request):
    try:
        source = request.app.state.runtime.index.get_source_excerpt(str(chunk_id))
    except KeyError as exc:
        raise HTTPException(404) from exc
    if source["document_id"] != str(document_id):
        raise HTTPException(404)
    return {**source, "url": f"/api/library/{document_id}/pdf#page={source['page_start']}"}
