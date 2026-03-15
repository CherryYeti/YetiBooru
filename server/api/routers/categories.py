from fastapi import APIRouter, HTTPException

from api.db import get_conn
from api.schemas import CreateCategoryRequest, UpdateCategoryRequest

router = APIRouter()


@router.get("/categories")
def get_categories():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, label, color, is_default FROM categories ORDER BY is_default DESC, id ASC"
        ).fetchall()
        return [{"id": r[0], "label": r[1], "color": r[2], "is_default": r[3]} for r in rows]


@router.post("/categories")
def create_category(req: CreateCategoryRequest):
    label = req.label.strip().lower()
    color = req.color.strip()

    if not label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")
    if not color:
        raise HTTPException(status_code=400, detail="Category color cannot be empty")

    with get_conn() as conn:
        has_default = conn.execute(
            "SELECT id FROM categories WHERE is_default = TRUE ORDER BY id ASC LIMIT 1"
        ).fetchone()
        should_be_default = has_default is None

        existing = conn.execute(
            "SELECT id FROM categories WHERE label = %s", (label,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Category already exists")

        row = conn.execute(
            """
            INSERT INTO categories (label, color, is_default)
            VALUES (%s, %s, %s)
            RETURNING id, label, color, is_default
            """,
            (label, color, should_be_default),
        ).fetchone()
        conn.commit()
        return {"id": row[0], "label": row[1], "color": row[2], "is_default": row[3]}


@router.put("/category/{category_label}")
def update_category(category_label: str, req: UpdateCategoryRequest):
    old_label = category_label.strip().lower()
    new_label = req.label.strip().lower()
    color = req.color.strip()

    if not new_label:
        raise HTTPException(status_code=400, detail="Category label cannot be empty")
    if not color:
        raise HTTPException(status_code=400, detail="Category color cannot be empty")

    with get_conn() as conn:
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
            RETURNING id, label, color, is_default
            """,
            (new_label, color, category_id),
        ).fetchone()
        conn.commit()

        return {"id": row[0], "label": row[1], "color": row[2], "is_default": row[3]}


@router.put("/category/{category_label}/default")
def set_default_category(category_label: str):
    label = category_label.strip().lower()

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM categories WHERE label = %s", (label,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Category not found")

        category_id = existing[0]
        conn.execute("UPDATE categories SET is_default = FALSE")
        row = conn.execute(
            """
            UPDATE categories
            SET is_default = TRUE
            WHERE id = %s
            RETURNING id, label, color, is_default
            """,
            (category_id,),
        ).fetchone()
        conn.commit()

        return {"id": row[0], "label": row[1], "color": row[2], "is_default": row[3]}
