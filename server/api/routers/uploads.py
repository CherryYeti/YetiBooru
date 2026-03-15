import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.authz import AuthUser, require_user
from api.db import get_conn
from api.services import (
    UPLOAD_CHUNK_SIZE,
    cleanup_upload,
    get_upload_paths,
    guess_media_ext,
    load_upload_meta,
    normalize_ext,
    normalize_optional_text,
    normalize_source_url,
    save_upload_meta,
    store_post_and_tags,
)

router = APIRouter()


@router.post("/upload")
async def upload_post(
    file: UploadFile = File(...),
    tags: str = Form(""),
    uploader_name: str | None = Form(None),
    source_url: str | None = Form(None),
    _: AuthUser = Depends(require_user),
):
    content_type = file.content_type or ""
    if content_type.startswith("image/"):
        post_type = "image"
    elif content_type.startswith("video/"):
        post_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    media_ext = guess_media_ext(post_type, content_type, file.filename)

    with get_conn() as conn:
        upload_id = str(uuid.uuid4())
        _, part_path = get_upload_paths(upload_id)
        with open(part_path, "wb") as out_file:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out_file.write(chunk)

        post_id = store_post_and_tags(
            conn,
            post_type,
            part_path,
            tags,
            media_ext,
            uploader_name,
            source_url,
        )
        conn.commit()
        return {"id": post_id}


@router.post("/upload/init")
async def init_upload(
    content_type: str = Form(...),
    filename: str = Form(""),
    uploader_name: str | None = Form(None),
    source_url: str | None = Form(None),
    _: AuthUser = Depends(require_user),
):
    if content_type.startswith("image/"):
        post_type = "image"
    elif content_type.startswith("video/"):
        post_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    media_ext = guess_media_ext(post_type, content_type, filename)

    upload_id = str(uuid.uuid4())
    meta = {
        "post_type": post_type,
        "media_ext": media_ext,
        "uploader_name": normalize_optional_text(uploader_name),
        "source_url": normalize_source_url(source_url),
        "next_chunk": 0,
        "received_bytes": 0,
    }
    save_upload_meta(upload_id, meta)
    return {"uploadId": upload_id, "chunkSize": UPLOAD_CHUNK_SIZE}


@router.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    _: AuthUser = Depends(require_user),
):
    meta = load_upload_meta(upload_id)
    expected_chunk = int(meta.get("next_chunk", 0))
    if chunk_index != expected_chunk:
        raise HTTPException(
            status_code=409,
            detail=f"Out-of-order chunk. Expected {expected_chunk}, got {chunk_index}",
        )

    _, part_path = get_upload_paths(upload_id)
    bytes_written = 0
    with open(part_path, "ab") as out_file:
        while True:
            block = await chunk.read(UPLOAD_CHUNK_SIZE)
            if not block:
                break
            out_file.write(block)
            bytes_written += len(block)

    meta["next_chunk"] = expected_chunk + 1
    meta["received_bytes"] = int(meta.get("received_bytes", 0)) + bytes_written
    save_upload_meta(upload_id, meta)

    return {
        "nextChunk": meta["next_chunk"],
        "receivedBytes": meta["received_bytes"],
    }


@router.post("/upload/complete")
async def complete_upload(
    upload_id: str = Form(...),
    tags: str = Form(""),
    _: AuthUser = Depends(require_user),
):
    meta = load_upload_meta(upload_id)
    post_type = meta.get("post_type")
    if post_type not in ("image", "video"):
        raise HTTPException(status_code=400, detail="Invalid upload session")
    media_ext = normalize_ext(str(meta.get("media_ext", ""))) or ("mp4" if post_type == "video" else "png")
    uploader_name = normalize_optional_text(meta.get("uploader_name"))
    source_url = normalize_source_url(meta.get("source_url"))

    _, part_path = get_upload_paths(upload_id)
    if not os.path.isfile(part_path):
        raise HTTPException(status_code=400, detail="No uploaded data found")

    try:
        with get_conn() as conn:
            post_id = store_post_and_tags(
                conn,
                post_type,
                part_path,
                tags,
                media_ext,
                uploader_name,
                source_url,
            )
            conn.commit()
            cleanup_upload(upload_id)
            return {"id": post_id}
    except Exception:
        raise


@router.delete("/upload/{upload_id}")
async def abort_upload(upload_id: str, _: AuthUser = Depends(require_user)):
    cleanup_upload(upload_id)
    return {"detail": "Upload session removed"}
