import os

from fastapi import APIRouter, HTTPException

from api.db import get_conn
from api.schemas import Post, UpdatePostTagsRequest
from api.services import build_tags_for_post, get_default_category_id, normalize_ext

router = APIRouter()


@router.get("/post/{post_id}")
def get_post(post_id: int):
    with get_conn() as conn:
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
        tags = build_tags_for_post(conn, row[0])
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


@router.get("/posts/")
def search_posts(query: str = ""):
    with get_conn() as conn:
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

            placeholders = ",".join(["%s"] * len(tags))
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
            tags = build_tags_for_post(conn, row[0])
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


@router.get("/posts/count")
def get_posts_count():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(id) FROM posts"
        ).fetchone()
        max_id = row[0] if row and row[0] else 0
        return {"maxId": max_id}


@router.get("/stats")
def get_stats():
    with get_conn() as conn:
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


@router.put("/post/{post_id}/tags")
def update_post_tags(post_id: int, req: UpdatePostTagsRequest):
    with get_conn() as conn:
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
                default_category_id = get_default_category_id(conn)
                row = conn.execute(
                    "INSERT INTO tags (label, category_id, count) VALUES (%s, %s, 0) RETURNING id",
                    (label, default_category_id),
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
            for row in impl_rows:
                implied_ids.add(row[0])

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

        return build_tags_for_post(conn, post_id)


@router.delete("/post/{post_id}")
def delete_post(post_id: int):
    with get_conn() as conn:
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
    ext = normalize_ext(row[2]) or ("mp4" if row[1] == "video" else "png")
    media_path = os.path.join(data_root, "media", f"{post_id}.{ext}")
    thumb_path = os.path.join(data_root, "thumbnail", f"{post_id}.png")
    for path in (media_path, thumb_path):
        if os.path.isfile(path):
            os.remove(path)

    return {"detail": f"Post {post_id} deleted successfully"}


@router.get("/post/{post_id}/next")
def get_next_post(post_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE id > %s ORDER BY id ASC LIMIT 1", (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No next post")
        return {"id": row[0]}


@router.get("/post/{post_id}/prev")
def get_prev_post(post_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE id < %s ORDER BY id DESC LIMIT 1", (post_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No previous post")
        return {"id": row[0]}
