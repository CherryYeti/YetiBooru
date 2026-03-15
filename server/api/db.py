import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg_pool import ConnectionPool

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
    del app
    global pool
    pool = ConnectionPool(DB_CONNINFO, min_size=2, max_size=10)
    with pool.connection() as conn:
        conn.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE")
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

        default_rows = conn.execute(
            "SELECT id FROM categories WHERE is_default = TRUE ORDER BY id ASC"
        ).fetchall()
        if len(default_rows) == 0:
            preferred = conn.execute(
                "SELECT id FROM categories WHERE label = 'general' ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if not preferred:
                preferred = conn.execute(
                    "SELECT id FROM categories ORDER BY id ASC LIMIT 1"
                ).fetchone()
            if preferred:
                conn.execute(
                    "UPDATE categories SET is_default = TRUE WHERE id = %s",
                    (preferred[0],),
                )
        elif len(default_rows) > 1:
            keep_id = default_rows[0][0]
            conn.execute("UPDATE categories SET is_default = FALSE WHERE id <> %s", (keep_id,))
            conn.execute("UPDATE categories SET is_default = TRUE WHERE id = %s", (keep_id,))
        conn.commit()
    yield
    if pool is not None:
        pool.close()


def get_conn():
    if pool is None:
        raise RuntimeError("Database pool has not been initialized")
    return pool.connection()
