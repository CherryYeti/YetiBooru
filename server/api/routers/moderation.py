import os

from fastapi import APIRouter, Depends, HTTPException

from api.authz import AuthUser, require_moderator, require_user
from api.db import get_conn
from api.schemas import CreatePostReportRequest, PostReportInfo, ResolvePostReportRequest
from api.services import normalize_ext

router = APIRouter()


def _report_from_row(row) -> PostReportInfo:
    return PostReportInfo(
        id=row[0],
        post_id=row[1],
        reporter_user_id=row[2],
        reporter_name=row[3],
        reason=row[4],
        status=row[5],
        resolution_note=row[6],
        created_at=row[7].isoformat(),
        resolved_at=row[8].isoformat() if row[8] else None,
        resolved_by_user_id=row[9],
        resolved_by_name=row[10],
    )


@router.post("/post/{post_id}/report")
def report_post(post_id: int, req: CreatePostReportRequest, user: AuthUser = Depends(require_user)):
    reason = req.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Please provide a clearer report reason")
    if len(reason) > 1000:
        raise HTTPException(status_code=400, detail="Report reason is too long")

    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM posts WHERE id = %s", (post_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Post not found")

        duplicate = conn.execute(
            """
            SELECT id
            FROM post_reports
            WHERE post_id = %s AND reporter_user_id = %s AND status = 'open'
            LIMIT 1
            """,
            (post_id, user.id),
        ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="You already have an open report for this post")

        row = conn.execute(
            """
            INSERT INTO post_reports (post_id, reporter_user_id, reason)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (post_id, user.id, reason),
        ).fetchone()
        conn.commit()

    return {"detail": "Report submitted", "reportId": row[0]}


@router.get("/moderation/reports")
def list_reports(
    status: str = "open",
    _: AuthUser = Depends(require_moderator),
):
    allowed_statuses = {"open", "resolved", "dismissed", "deleted", "all"}
    normalized = status.strip().lower()
    if normalized not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid report status filter")

    with get_conn() as conn:
        if normalized == "all":
            rows = conn.execute(
                """
                SELECT r.id,
                       r.post_id,
                       r.reporter_user_id,
                       reporter.name,
                       r.reason,
                       r.status,
                       r.resolution_note,
                       r.created_at,
                       r.resolved_at,
                       r.resolved_by_user_id,
                       resolver.name
                FROM post_reports r
                LEFT JOIN "user" reporter ON reporter.id = r.reporter_user_id
                LEFT JOIN "user" resolver ON resolver.id = r.resolved_by_user_id
                ORDER BY r.created_at DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.id,
                       r.post_id,
                       r.reporter_user_id,
                       reporter.name,
                       r.reason,
                       r.status,
                       r.resolution_note,
                       r.created_at,
                       r.resolved_at,
                       r.resolved_by_user_id,
                       resolver.name
                FROM post_reports r
                LEFT JOIN "user" reporter ON reporter.id = r.reporter_user_id
                LEFT JOIN "user" resolver ON resolver.id = r.resolved_by_user_id
                WHERE r.status = %s
                ORDER BY r.created_at DESC
                """,
                (normalized,),
            ).fetchall()

    return [_report_from_row(row) for row in rows]


@router.put("/moderation/reports/{report_id}")
def resolve_report(
    report_id: int,
    req: ResolvePostReportRequest,
    actor: AuthUser = Depends(require_moderator),
):
    action = req.action.strip().lower()
    if action not in {"resolved", "dismissed", "deleted"}:
        raise HTTPException(status_code=400, detail="Invalid moderation action")

    with get_conn() as conn:
        report_row = conn.execute(
            "SELECT id, post_id, status FROM post_reports WHERE id = %s",
            (report_id,),
        ).fetchone()
        if not report_row:
            raise HTTPException(status_code=404, detail="Report not found")

        if report_row[2] != "open":
            raise HTTPException(status_code=409, detail="Report has already been closed")

        if action == "deleted":
            if report_row[1] is not None:
                post_row = conn.execute(
                    """
                    SELECT id, type,
                           COALESCE(media_ext, CASE WHEN type = 'video' THEN 'mp4' ELSE 'png' END) AS media_ext
                    FROM posts
                    WHERE id = %s
                    """,
                    (report_row[1],),
                ).fetchone()

                if post_row:
                    tag_ids = [
                        r[0]
                        for r in conn.execute(
                            "SELECT tag_id FROM post_tags WHERE post_id = %s", (report_row[1],)
                        ).fetchall()
                    ]

                    conn.execute("DELETE FROM posts WHERE id = %s", (report_row[1],))

                    for tid in tag_ids:
                        conn.execute(
                            "UPDATE tags SET count = (SELECT COUNT(*) FROM post_tags WHERE tag_id = %s) WHERE id = %s",
                            (tid, tid),
                        )

                    data_root = os.environ.get("DATA_ROOT", "/data")
                    ext = normalize_ext(post_row[2]) or ("mp4" if post_row[1] == "video" else "png")
                    media_path = os.path.join(data_root, "media", f"{report_row[1]}.{ext}")
                    thumb_path = os.path.join(data_root, "thumbnail", f"{report_row[1]}.png")
                    for path in (media_path, thumb_path):
                        if os.path.isfile(path):
                            os.remove(path)

        conn.execute(
            """
            UPDATE post_reports
            SET status = %s,
                resolution_note = %s,
                resolved_at = CURRENT_TIMESTAMP,
                resolved_by_user_id = %s
            WHERE id = %s
            """,
            (action, req.note.strip() if req.note else None, actor.id, report_id),
        )
        conn.commit()

        updated = conn.execute(
            """
            SELECT r.id,
                   r.post_id,
                   r.reporter_user_id,
                   reporter.name,
                   r.reason,
                   r.status,
                   r.resolution_note,
                   r.created_at,
                   r.resolved_at,
                   r.resolved_by_user_id,
                   resolver.name
            FROM post_reports r
            LEFT JOIN "user" reporter ON reporter.id = r.reporter_user_id
            LEFT JOIN "user" resolver ON resolver.id = r.resolved_by_user_id
            WHERE r.id = %s
            """,
            (report_id,),
        ).fetchone()

    return _report_from_row(updated)
