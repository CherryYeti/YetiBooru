import json
import os
import subprocess

from fastapi import HTTPException

from api.schemas import Category, Tag

UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024


def get_upload_paths(upload_id: str):
    data_root = os.environ.get("DATA_ROOT", "/data")
    upload_dir = os.path.join(data_root, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return (
        os.path.join(upload_dir, f"{upload_id}.meta.json"),
        os.path.join(upload_dir, f"{upload_id}.part"),
    )


def load_upload_meta(upload_id: str) -> dict:
    meta_path, _ = get_upload_paths(upload_id)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Upload session not found") from e


def save_upload_meta(upload_id: str, meta: dict):
    meta_path, _ = get_upload_paths(upload_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def cleanup_upload(upload_id: str):
    meta_path, part_path = get_upload_paths(upload_id)
    for path in (meta_path, part_path):
        if os.path.isfile(path):
            os.remove(path)


def normalize_ext(ext: str) -> str:
    normalized = ext.strip().lower().lstrip(".")
    if not normalized or len(normalized) > 10 or not normalized.isalnum():
        return ""
    return normalized


def guess_media_ext(post_type: str, content_type: str, filename: str | None) -> str:
    ct = (content_type or "").lower()
    image_by_type = {
        "image/gif": "gif",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/bmp": "bmp",
    }
    video_by_type = {
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/quicktime": "mov",
        "video/x-matroska": "mkv",
    }

    if post_type == "image" and ct in image_by_type:
        return image_by_type[ct]
    if post_type == "video" and ct in video_by_type:
        return video_by_type[ct]

    if filename and "." in filename:
        candidate = normalize_ext(filename.rsplit(".", 1)[1])
        if candidate:
            return candidate

    return "mp4" if post_type == "video" else "png"


def probe_media_dimensions(media_path: str) -> tuple[int | None, int | None]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        media_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, None

    parsed = (result.stdout or "").strip().split("x")
    if len(parsed) != 2:
        return None, None

    try:
        width = int(parsed[0])
        height = int(parsed[1])
        return width, height
    except ValueError:
        return None, None


def normalize_source_url(source_url: str | None) -> str | None:
    if source_url is None:
        return None
    normalized = source_url.strip()
    return normalized if normalized else None


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def get_default_category_id(conn) -> int:
    default_row = conn.execute(
        "SELECT id FROM categories WHERE is_default = TRUE ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if default_row:
        return default_row[0]

    fallback_row = conn.execute(
        "SELECT id FROM categories ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if not fallback_row:
        raise HTTPException(status_code=500, detail="No categories exist")

    conn.execute("UPDATE categories SET is_default = TRUE WHERE id = %s", (fallback_row[0],))
    return fallback_row[0]


def build_tags_for_post(conn, post_id: int) -> list[Tag]:
    rows = conn.execute(
        """
        SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
        FROM post_tags pt
        JOIN tags t ON t.id = pt.tag_id
        JOIN categories c ON c.id = t.category_id
        WHERE pt.post_id = %s
        ORDER BY t.label
        """,
        (post_id,),
    ).fetchall()
    return [
        Tag(id=r[0], label=r[1], count=r[2], category=Category(label=r[3], color=r[4]))
        for r in rows
    ]


def get_implications(conn, tag_id: int) -> list[Tag]:
    rows = conn.execute(
        """
        SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
        FROM tag_implications ti
        JOIN tags t ON t.id = ti.child_tag_id
        JOIN categories c ON c.id = t.category_id
        WHERE ti.parent_tag_id = %s
        ORDER BY t.label
        """,
        (tag_id,),
    ).fetchall()
    return [
        Tag(id=r[0], label=r[1], count=r[2], category=Category(label=r[3], color=r[4]))
        for r in rows
    ]


def store_post_and_tags(
    conn,
    post_type: str,
    media_path: str,
    tags: str,
    media_ext: str,
    uploader_name: str | None,
    source_url: str | None,
):
    row = conn.execute(
        """
        INSERT INTO posts (score, type, media_ext, uploader_name, source_url)
        VALUES (0, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            post_type,
            media_ext,
            normalize_optional_text(uploader_name),
            normalize_source_url(source_url),
        ),
    ).fetchone()
    post_id = row[0]

    data_root = os.environ.get("DATA_ROOT", "/data")
    media_dir = os.path.join(data_root, "media")
    thumb_dir = os.path.join(data_root, "thumbnail")
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    ext = normalize_ext(media_ext) or ("mp4" if post_type == "video" else "png")
    final_media_path = os.path.join(media_dir, f"{post_id}.{ext}")
    os.replace(media_path, final_media_path)
    media_width, media_height = probe_media_dimensions(final_media_path)
    conn.execute(
        "UPDATE posts SET media_width = %s, media_height = %s WHERE id = %s",
        (media_width, media_height, post_id),
    )

    thumb_path = os.path.join(thumb_dir, f"{post_id}.png")
    ffmpeg_cmd = ["ffmpeg", "-i", final_media_path, "-vframes", "1", "-vf", "scale=300:-1", thumb_path]
    ffmpeg_result = subprocess.run(ffmpeg_cmd, capture_output=True)
    if ffmpeg_result.returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    tag_labels = [t.strip().lower() for t in tags.split() if t.strip()]
    for label in tag_labels:
        tag_row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (label,)
        ).fetchone()
        if not tag_row:
            default_category_id = get_default_category_id(conn)
            tag_row = conn.execute(
                "INSERT INTO tags (label, category_id, count) VALUES (%s, %s, 0) RETURNING id",
                (label, default_category_id),
            ).fetchone()
        conn.execute(
            "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (post_id, tag_row[0]),
        )
        conn.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
            (tag_row[0], tag_row[0]),
        )

    return post_id
