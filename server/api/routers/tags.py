from fastapi import APIRouter, Depends, HTTPException

from api.authz import AuthUser, require_admin, require_moderator
from api.db import get_conn
from api.schemas import Category, CreateTagRequest, Tag, UpdateImplicationsRequest, UpdateTagRequest
from api.services import get_default_category_id, get_implications

router = APIRouter()


@router.get("/tags/")
def search_tags(query: str = ""):
    with get_conn() as conn:
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


@router.post("/tags/")
def create_tag(req: CreateTagRequest, _: AuthUser = Depends(require_moderator)):
    label = req.label.strip().lower()
    if not label:
        raise HTTPException(status_code=400, detail="Tag label cannot be empty")

    with get_conn() as conn:
        category_id = req.category_id if req.category_id is not None else get_default_category_id(conn)
        cat_row = conn.execute(
            "SELECT id, label, color FROM categories WHERE id = %s", (category_id,)
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
            (label, category_id),
        ).fetchone()
        conn.commit()

        return Tag(
            id=row[0],
            label=label,
            count=0,
            category=Category(label=cat_row[1], color=cat_row[2]),
        )


@router.get("/tag/{tag}")
def get_tag(tag: str):
    with get_conn() as conn:
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


@router.get("/tag/{tag}/implications")
def get_tag_implications(tag: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM tags WHERE label = %s", (tag,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        return get_implications(conn, row[0])


@router.put("/tag/{tag}/implications")
def update_tag_implications(
    tag: str,
    req: UpdateImplicationsRequest,
    _: AuthUser = Depends(require_moderator),
):
    with get_conn() as conn:
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

        return get_implications(conn, parent_id)


@router.put("/tag/{tag}")
def update_tag(tag: str, req: UpdateTagRequest, _: AuthUser = Depends(require_moderator)):
    category_label = req.category_label.strip().lower()
    if not category_label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")

    with get_conn() as conn:
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


@router.delete("/tag/{tag}")
def delete_tag(tag: str, _: AuthUser = Depends(require_admin)):
    with get_conn() as conn:
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
