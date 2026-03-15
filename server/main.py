import os
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from psycopg_pool import ConnectionPool
import subprocess

DB_CONNINFO = (
    f"host={os.environ.get('DB_HOST', 'db')} "
    f"port={os.environ.get('DB_PORT', '5432')} "
    f"dbname={os.environ.get('DB_NAME', 'booru')} "
    f"user={os.environ.get('DB_USER', 'booru')} "
    f"password={os.environ.get('DB_PASSWORD', 'booru')}"
)

pool: ConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = ConnectionPool(DB_CONNINFO, min_size=2, max_size=10)
    with pool.connection() as conn:
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS media_ext VARCHAR(10)")
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMPTZ")
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS uploader_name TEXT")
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS media_width INTEGER")
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS media_height INTEGER")
        conn.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_url TEXT")
        conn.execute(
            """
            UPDATE posts
            SET media_ext = CASE WHEN type = 'video' THEN 'mp4' ELSE 'png' END
            WHERE media_ext IS NULL OR media_ext = ''
            """
        )
        conn.execute(
            """
            UPDATE posts
            SET uploaded_at = CURRENT_TIMESTAMP
            WHERE uploaded_at IS NULL
            """
        )
        conn.execute("ALTER TABLE posts ALTER COLUMN uploaded_at SET DEFAULT CURRENT_TIMESTAMP")
        conn.execute("ALTER TABLE posts ALTER COLUMN uploaded_at SET NOT NULL")
        conn.commit()
    yield
    pool.close()


app = FastAPI(lifespan=lifespan)


@dataclass
class Category:
    label: str
    color: str


@dataclass
class Tag:
    category: Category
    count: int
    label: str
    id: int


@dataclass
class Post:
    id: int
    score: int
    tags: list[Tag]
    type: Literal["video", "image"]
    media_ext: str
    uploaded_at: str
    uploader_name: str | None
    media_width: int | None
    media_height: int | None
    source_url: str | None

class CreateTagRequest(BaseModel):
    label: str
    category_id: int

class UpdateImplicationsRequest(BaseModel):
    implied_tag_labels: list[str]

class UpdateTagRequest(BaseModel):
    category_label: str

class CreateCategoryRequest(BaseModel):
    label: str
    color: str

class UpdateCategoryRequest(BaseModel):
    label: str
    color: str

class UpdatePostTagsRequest(BaseModel):
    tag_labels: list[str]


UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024

def _get_conn():
    return pool.connection()


def _get_upload_paths(upload_id: str):
    data_root = os.environ.get("DATA_ROOT", "/data")
    upload_dir = os.path.join(data_root, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return (
        os.path.join(upload_dir, f"{upload_id}.meta.json"),
        os.path.join(upload_dir, f"{upload_id}.part"),
    )


def _load_upload_meta(upload_id: str) -> dict:
    meta_path, _ = _get_upload_paths(upload_id)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Upload session not found") from e


def _save_upload_meta(upload_id: str, meta: dict):
    meta_path, _ = _get_upload_paths(upload_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def _cleanup_upload(upload_id: str):
    meta_path, part_path = _get_upload_paths(upload_id)
    for path in (meta_path, part_path):
        if os.path.isfile(path):
            os.remove(path)


def _normalize_ext(ext: str) -> str:
    normalized = ext.strip().lower().lstrip(".")
    if not normalized or len(normalized) > 10 or not normalized.isalnum():
        return ""
    return normalized


def _guess_media_ext(post_type: str, content_type: str, filename: str | None) -> str:
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
        candidate = _normalize_ext(filename.rsplit(".", 1)[1])
        if candidate:
            return candidate

    return "mp4" if post_type == "video" else "png"


def _probe_media_dimensions(media_path: str) -> tuple[int | None, int | None]:
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


def _normalize_source_url(source_url: str | None) -> str | None:
    if source_url is None:
        return None
    normalized = source_url.strip()
    return normalized if normalized else None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _store_post_and_tags(
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
            _normalize_optional_text(uploader_name),
            _normalize_source_url(source_url),
        ),
    ).fetchone()
    post_id = row[0]

    data_root = os.environ.get("DATA_ROOT", "/data")
    media_dir = os.path.join(data_root, "media")
    thumb_dir = os.path.join(data_root, "thumbnail")
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    ext = _normalize_ext(media_ext) or ("mp4" if post_type == "video" else "png")
    final_media_path = os.path.join(media_dir, f"{post_id}.{ext}")
    os.replace(media_path, final_media_path)
    media_width, media_height = _probe_media_dimensions(final_media_path)
    conn.execute(
        "UPDATE posts SET media_width = %s, media_height = %s WHERE id = %s",
        (media_width, media_height, post_id),
    )

    thumb_path = os.path.join(thumb_dir, f"{post_id}.png")
    if post_type == "video":
        ffmpeg_cmd = ["ffmpeg", "-i", final_media_path, "-vframes", "1", "-vf", "scale=300:-1", thumb_path]
    else:
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
            default_cat = conn.execute(
                "SELECT id FROM categories ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not default_cat:
                raise HTTPException(status_code=500, detail="No categories exist")
            tag_row = conn.execute(
                "INSERT INTO tags (label, category_id, count) VALUES (%s, %s, 0) RETURNING id",
                (label, default_cat[0]),
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


def _build_tags_for_post(conn, post_id: int) -> list[Tag]:
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


def _get_implications(conn, tag_id: int) -> list[Tag]:
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


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/post/{post_id}")
def get_post(post_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, score, type,
                   COALESCE(media_ext, CASE WHEN type = 'video' THEN 'mp4' ELSE 'png' END) AS media_ext,
                     uploaded_at, uploader_name, media_width, media_height, source_url
            FROM posts
            WHERE id = %s
            """,
            (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        tags = _build_tags_for_post(conn, row[0])
        return Post(
            id=row[0],
            score=row[1],
            type=row[2],
            media_ext=row[3],
            uploaded_at=row[4].isoformat(),
            uploader_name=row[5],
            media_width=row[6],
            media_height=row[7],
            source_url=row[8],
            tags=tags,
        )


@app.get("/posts/")
def search_posts(query: str = ""):
    with _get_conn() as conn:
        if not query:
            rows = conn.execute(
                """
                SELECT id, score, type,
                       COALESCE(media_ext, CASE WHEN type = 'video' THEN 'mp4' ELSE 'png' END) AS media_ext,
                      uploaded_at, uploader_name, media_width, media_height, source_url
                FROM posts
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()
        else:
            tags = [tag.strip().lower() for tag in query.split()]
            
            placeholders = ','.join(['%s'] * len(tags))
            rows = conn.execute(
                f"""
                  SELECT p.id, p.score, p.type,
                      COALESCE(p.media_ext, CASE WHEN p.type = 'video' THEN 'mp4' ELSE 'png' END) AS media_ext,
                        p.uploaded_at, p.uploader_name, p.media_width, p.media_height, p.source_url
                FROM posts p
                WHERE p.id IN (
                    SELECT pt.post_id
                    FROM post_tags pt
                    JOIN tags t ON t.id = pt.tag_id
                    WHERE LOWER(t.label) IN ({placeholders})
                    GROUP BY pt.post_id
                    HAVING COUNT(DISTINCT t.id) = %s
                )
                ORDER BY p.id DESC
                LIMIT 50
                """,
                (*tags, len(tags))
            ).fetchall()
        
        posts = []
        for row in rows:
            tags = _build_tags_for_post(conn, row[0])
            posts.append(
                Post(
                    id=row[0],
                    score=row[1],
                    type=row[2],
                    media_ext=row[3],
                    uploaded_at=row[4].isoformat(),
                    uploader_name=row[5],
                    media_width=row[6],
                    media_height=row[7],
                    source_url=row[8],
                    tags=tags,
                )
            )
        return posts


@app.get("/tags/")
def search_tags(query: str = ""):
    with _get_conn() as conn:
        if query:
            rows = conn.execute(
                """
                SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
                FROM tags t
                JOIN categories c ON c.id = t.category_id
                WHERE t.label ILIKE %s
                ORDER BY t.count DESC
                LIMIT 50
                """,
                (f"%{query}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
                FROM tags t
                JOIN categories c ON c.id = t.category_id
                ORDER BY t.count DESC
                LIMIT 50
                """
            ).fetchall()
        return [
            Tag(id=r[0], label=r[1], count=r[2], category=Category(label=r[3], color=r[4]))
            for r in rows
        ]


@app.post("/tags/")
def create_tag(req: CreateTagRequest):
    label = req.label.strip().lower()
    if not label:
        raise HTTPException(status_code=400, detail="Tag label cannot be empty")

    with _get_conn() as conn:
        cat_row = conn.execute(
            "SELECT id, label, color FROM categories WHERE id = %s", (req.category_id,)
        ).fetchone()
        if not cat_row:
            raise HTTPException(status_code=400, detail="Category not found")

        existing = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (label,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Tag already exists")

        row = conn.execute(
            "INSERT INTO tags (label, category_id, count) VALUES (%s, %s, 0) RETURNING id",
            (label, req.category_id),
        ).fetchone()
        conn.commit()

        return Tag(
            id=row[0],
            label=label,
            count=0,
            category=Category(label=cat_row[1], color=cat_row[2]),
        )

@app.get("/tag/{tag}")
def get_tag(tag: str):
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
            FROM tags t
            JOIN categories c ON c.id = t.category_id
            WHERE t.label = %s
            """,
            (tag,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        return Tag(id=row[0], label=row[1], count=row[2], category=Category(label=row[3], color=row[4]))


@app.get("/tag/{tag}/implications")
def get_tag_implications(tag: str):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (tag,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        return _get_implications(conn, row[0])


@app.put("/tag/{tag}/implications")
def update_tag_implications(tag: str, req: UpdateImplicationsRequest):
    with _get_conn() as conn:
        parent_row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (tag,)
        ).fetchone()
        if not parent_row:
            raise HTTPException(status_code=404, detail="Tag not found")
        parent_id = parent_row[0]

        child_ids = []
        for label in req.implied_tag_labels:
            label = label.strip().lower()
            if not label:
                continue
            child_row = conn.execute(
                "SELECT id FROM tags WHERE label = %s", (label,)
            ).fetchone()
            if not child_row:
                raise HTTPException(status_code=400, detail=f"Tag '{label}' not found")
            if child_row[0] == parent_id:
                raise HTTPException(status_code=400, detail="A tag cannot imply itself")
            child_ids.append(child_row[0])

        conn.execute(
            "DELETE FROM tag_implications WHERE parent_tag_id = %s", (parent_id,)
        )
        for child_id in child_ids:
            conn.execute(
                "INSERT INTO tag_implications (parent_tag_id, child_tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (parent_id, child_id),
            )

        post_ids = [
            r[0] for r in conn.execute(
                "SELECT post_id FROM post_tags WHERE tag_id = %s", (parent_id,)
            ).fetchall()
        ]
        for child_id in child_ids:
            for pid in post_ids:
                conn.execute(
                    "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (pid, child_id),
                )
            conn.execute(
                "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
                (child_id, child_id),
            )

        conn.commit()

        return _get_implications(conn, parent_id)

@app.put("/tag/{tag}")
def update_tag(tag: str, req: UpdateTagRequest):
    category_label = req.category_label.strip().lower()
    if not category_label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")

    with _get_conn() as conn:
        tag_row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (tag,)
        ).fetchone()
        if not tag_row:
            raise HTTPException(status_code=404, detail="Tag not found")

        cat_row = conn.execute(
            "SELECT id, label, color FROM categories WHERE label = %s", (category_label,)
        ).fetchone()
        if not cat_row:
            raise HTTPException(status_code=400, detail="Category not found")

        conn.execute(
            "UPDATE tags SET category_id = %s WHERE id = %s",
            (cat_row[0], tag_row[0]),
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT t.id, t.label, t.count, c.label AS cat_label, c.color AS cat_color
            FROM tags t
            JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s
            """,
            (tag_row[0],),
        ).fetchone()

        return Tag(
            id=row[0],
            label=row[1],
            count=row[2],
            category=Category(label=row[3], color=row[4]),
        )


@app.get("/categories")
def get_categories():
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, label, color FROM categories ORDER BY id"
        ).fetchall()
        return [{"id": r[0], "label": r[1], "color": r[2]} for r in rows]


@app.post("/categories")
def create_category(req: CreateCategoryRequest):
    label = req.label.strip().lower()
    color = req.color.strip()

    if not label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")
    if not color:
        raise HTTPException(status_code=400, detail="Category color cannot be empty")

    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM categories WHERE label = %s", (label,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Category already exists")

        row = conn.execute(
            """
            INSERT INTO categories (label, color)
            VALUES (%s, %s)
            RETURNING id, label, color
            """,
            (label, color),
        ).fetchone()
        conn.commit()
        return {"id": row[0], "label": row[1], "color": row[2]}


@app.put("/category/{category_label}")
def update_category(category_label: str, req: UpdateCategoryRequest):
    old_label = category_label.strip().lower()
    new_label = req.label.strip().lower()
    color = req.color.strip()

    if not new_label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")
    if not color:
        raise HTTPException(status_code=400, detail="Category color cannot be empty")

    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM categories WHERE label = %s", (old_label,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Category not found")

        category_id = existing[0]

        if new_label != old_label:
            duplicate = conn.execute(
                "SELECT id FROM categories WHERE label = %s", (new_label,)
            ).fetchone()
            if duplicate:
                raise HTTPException(status_code=409, detail="Category label already exists")

        row = conn.execute(
            """
            UPDATE categories
            SET label = %s, color = %s
            WHERE id = %s
            RETURNING id, label, color
            """,
            (new_label, color, category_id),
        ).fetchone()
        conn.commit()

        return {"id": row[0], "label": row[1], "color": row[2]}


@app.get("/posts/count")
def get_posts_count():
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(id) FROM posts"
        ).fetchone()
        max_id = row[0] if row and row[0] else 0
        return {"maxId": max_id}


@app.get("/stats")
def get_stats():
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM posts").fetchone()
        post_count = row[0] if row else 0

    data_root = os.environ.get("DATA_ROOT", "/data")
    media_dir = os.path.join(data_root, "media")
    total_bytes = 0
    if os.path.isdir(media_dir):
        for entry in os.scandir(media_dir):
            if entry.is_file():
                total_bytes += entry.stat().st_size

    return {"postCount": post_count, "totalBytes": total_bytes}

@app.put("/post/{post_id}/tags")
def update_post_tags(post_id: int, req: UpdatePostTagsRequest):
    with _get_conn() as conn:
        post_row = conn.execute(
            "SELECT id FROM posts WHERE id = %s", (post_id,)
        ).fetchone()
        if not post_row:
            raise HTTPException(status_code=404, detail="Post not found")

        tag_ids = []
        for label in req.tag_labels:
            label = label.strip().lower()
            if not label:
                continue
            row = conn.execute(
                "SELECT id FROM tags WHERE label = %s", (label,)
            ).fetchone()
            if not row:
                default_cat = conn.execute(
                    "SELECT id FROM categories ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not default_cat:
                    raise HTTPException(status_code=500, detail="No categories exist")
                row = conn.execute(
                    "INSERT INTO tags (label, category_id, count) VALUES (%s, %s, 0) RETURNING id",
                    (label, default_cat[0]),
                ).fetchone()
            tag_ids.append(row[0])

        old_tag_ids = [
            r[0] for r in conn.execute(
                "SELECT tag_id FROM post_tags WHERE post_id = %s", (post_id,)
            ).fetchall()
        ]

        conn.execute("DELETE FROM post_tags WHERE post_id = %s", (post_id,))
        for tid in tag_ids:
            conn.execute(
                "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (post_id, tid),
            )

        all_affected = set(old_tag_ids) | set(tag_ids)
        for tid in all_affected:
            conn.execute(
                "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
                (tid, tid),
            )

        implied_ids = set()
        for tid in tag_ids:
            impl_rows = conn.execute(
                "SELECT child_tag_id FROM tag_implications WHERE parent_tag_id = %s", (tid,)
            ).fetchall()
            for r in impl_rows:
                implied_ids.add(r[0])

        for impl_id in implied_ids:
            conn.execute(
                "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (post_id, impl_id),
            )
            conn.execute(
                "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
                (impl_id, impl_id),
            )

        conn.commit()

        return _build_tags_for_post(conn, post_id)

@app.delete("/tag/{tag}")
def delete_tag(tag: str):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (tag,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")

        tag_id = row[0]

        conn.execute("DELETE FROM post_tags WHERE tag_id = %s", (tag_id,))

        conn.execute("DELETE FROM tag_implications WHERE parent_tag_id = %s OR child_tag_id = %s", (tag_id, tag_id))

        conn.execute("DELETE FROM tags WHERE id = %s", (tag_id,))
        conn.commit()

        return {"detail": f"Tag '{tag}' deleted successfully"}

@app.delete("/post/{post_id}")
def delete_post(post_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, type,
                   COALESCE(media_ext, CASE WHEN type = 'video' THEN 'mp4' ELSE 'png' END) AS media_ext
            FROM posts
            WHERE id = %s
            """,
            (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        tag_ids = [
            r[0] for r in conn.execute(
                "SELECT tag_id FROM post_tags WHERE post_id = %s", (post_id,)
            ).fetchall()
        ]

        conn.execute("DELETE FROM posts WHERE id = %s", (post_id,))

        for tid in tag_ids:
            conn.execute(
                "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
                (tid, tid),
            )

        conn.commit()

    data_root = os.environ.get("DATA_ROOT", "/data")
    ext = _normalize_ext(row[2]) or ("mp4" if row[1] == "video" else "png")
    media_path = os.path.join(data_root, "media", f"{post_id}.{ext}")
    thumb_path = os.path.join(data_root, "thumbnail", f"{post_id}.png")
    for path in (media_path, thumb_path):
        if os.path.isfile(path):
            os.remove(path)

    return {"detail": f"Post {post_id} deleted successfully"}


@app.get("/post/{post_id}/next")
def get_next_post(post_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE id > %s ORDER BY id ASC LIMIT 1", (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No next post")
        return {"id": row[0]}


@app.get("/post/{post_id}/prev")
def get_prev_post(post_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE id < %s ORDER BY id DESC LIMIT 1", (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No previous post")
        return {"id": row[0]}

@app.post("/upload")
async def upload_post(
    file: UploadFile = File(...),
    tags: str = Form(""),
    uploader_name: str | None = Form(None),
    source_url: str | None = Form(None),
):
    content_type = file.content_type or ""
    if content_type.startswith("image/"):
        post_type = "image"
    elif content_type.startswith("video/"):
        post_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    media_ext = _guess_media_ext(post_type, content_type, file.filename)

    with _get_conn() as conn:
        upload_id = str(uuid.uuid4())
        _, part_path = _get_upload_paths(upload_id)
        with open(part_path, "wb") as out_file:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out_file.write(chunk)

        post_id = _store_post_and_tags(
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


@app.post("/upload/init")
async def init_upload(
    content_type: str = Form(...),
    filename: str = Form(""),
    uploader_name: str | None = Form(None),
    source_url: str | None = Form(None),
):
    if content_type.startswith("image/"):
        post_type = "image"
    elif content_type.startswith("video/"):
        post_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    media_ext = _guess_media_ext(post_type, content_type, filename)

    upload_id = str(uuid.uuid4())
    meta = {
        "post_type": post_type,
        "media_ext": media_ext,
        "uploader_name": _normalize_optional_text(uploader_name),
        "source_url": _normalize_source_url(source_url),
        "next_chunk": 0,
        "received_bytes": 0,
    }
    _save_upload_meta(upload_id, meta)
    return {"uploadId": upload_id, "chunkSize": UPLOAD_CHUNK_SIZE}


@app.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
):
    meta = _load_upload_meta(upload_id)
    expected_chunk = int(meta.get("next_chunk", 0))
    if chunk_index != expected_chunk:
        raise HTTPException(
            status_code=409,
            detail=f"Out-of-order chunk. Expected {expected_chunk}, got {chunk_index}",
        )

    _, part_path = _get_upload_paths(upload_id)
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
    _save_upload_meta(upload_id, meta)

    return {
        "nextChunk": meta["next_chunk"],
        "receivedBytes": meta["received_bytes"],
    }


@app.post("/upload/complete")
async def complete_upload(upload_id: str = Form(...), tags: str = Form("")):
    meta = _load_upload_meta(upload_id)
    post_type = meta.get("post_type")
    if post_type not in ("image", "video"):
        raise HTTPException(status_code=400, detail="Invalid upload session")
    media_ext = _normalize_ext(str(meta.get("media_ext", ""))) or ("mp4" if post_type == "video" else "png")
    uploader_name = _normalize_optional_text(meta.get("uploader_name"))
    source_url = _normalize_source_url(meta.get("source_url"))

    _, part_path = _get_upload_paths(upload_id)
    if not os.path.isfile(part_path):
        raise HTTPException(status_code=400, detail="No uploaded data found")

    try:
        with _get_conn() as conn:
            post_id = _store_post_and_tags(
                conn,
                post_type,
                part_path,
                tags,
                media_ext,
                uploader_name,
                source_url,
            )
            conn.commit()
            _cleanup_upload(upload_id)
            return {"id": post_id}
    except Exception:
        raise


@app.delete("/upload/{upload_id}")
async def abort_upload(upload_id: str):
    _cleanup_upload(upload_id)
    return {"detail": "Upload session removed"}

