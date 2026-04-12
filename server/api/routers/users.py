from fastapi import APIRouter, Depends, HTTPException

from api.authz import AuthUser, require_admin, require_moderator, require_user
from api.db import get_conn, get_owner_count, get_owner_emails, sync_bootstrap_owner_roles
from api.schemas import UpdateUserBanRequest, UpdateUserRoleRequest, UserInfo

router = APIRouter()


ROLE_WEIGHT = {
    "user": 1,
    "moderator": 2,
    "admin": 3,
    "owner": 4,
}


def _normalize_role(raw_role: str | None) -> str:
    role = (raw_role or "user").strip().lower()
    if role == "mod":
        role = "moderator"
    if role not in ROLE_WEIGHT:
        role = "user"
    return role


def _to_user_info(row) -> UserInfo:
    ban_expires = row[7].isoformat() if row[7] else None
    return UserInfo(
        id=row[0],
        name=row[1],
        email=row[2],
        role=_normalize_role(row[3]),
        banned=bool(row[4]),
        ban_reason=row[5],
        ban_expires=ban_expires,
    )


def _get_owner_count(conn) -> int:
    return get_owner_count(conn)


def _get_current_user_row(conn, user_id: str):
    return conn.execute(
        """
        SELECT id, name, email, role, COALESCE(banned, FALSE), "banReason", "createdAt", "banExpires"
        FROM "user"
        WHERE id = %s
        """,
        (user_id,),
    ).fetchone()


@router.get("/users/me")
def get_me(user: AuthUser = Depends(require_user)):
    with get_conn() as conn:
        sync_bootstrap_owner_roles(conn, user.email)
        row = _get_current_user_row(conn, user.id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _to_user_info(row)


@router.get("/users/bootstrap")
def get_bootstrap_status(user: AuthUser = Depends(require_user)):
    with get_conn() as conn:
        sync_bootstrap_owner_roles(conn, user.email)
        owner_count = _get_owner_count(conn)
        owner_emails = get_owner_emails()
        row = _get_current_user_row(conn, user.id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        current_role = _normalize_role(row[3])
        can_bootstrap = current_role != "owner" and (
            (owner_emails and user.email.lower() in owner_emails) or (not owner_emails and owner_count == 0)
        )

        return {
            "currentUser": _to_user_info(row),
            "ownerCount": owner_count,
            "ownerEmails": owner_emails,
            "canBootstrap": can_bootstrap,
            "bootstrapRequired": owner_count == 0,
        }


@router.post("/users/bootstrap")
def bootstrap_owner(user: AuthUser = Depends(require_user)):
    with get_conn() as conn:
        owner_emails = get_owner_emails()
        owner_count = _get_owner_count(conn)
        email = user.email.lower()

        if owner_emails:
            if email not in owner_emails:
                raise HTTPException(status_code=403, detail="This account is not authorized to become owner")
        elif owner_count > 0:
            raise HTTPException(status_code=400, detail="An owner already exists")

        sync_bootstrap_owner_roles(conn, user.email)
        conn.execute(
            'UPDATE "user" SET role = \'owner\' WHERE id = %s',
            (user.id,),
        )
        conn.commit()

        updated = _get_current_user_row(conn, user.id)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return _to_user_info(updated)


@router.get("/users")
def list_users(_: AuthUser = Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, email, role, COALESCE(banned, FALSE), "banReason", "createdAt", "banExpires"
            FROM "user"
            ORDER BY "createdAt" ASC
            """
        ).fetchall()
        return [_to_user_info(row) for row in rows]


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UpdateUserRoleRequest,
    actor: AuthUser = Depends(require_admin),
):
    target_role = _normalize_role(req.role)

    with get_conn() as conn:
        target_row = conn.execute(
            "SELECT id, role FROM \"user\" WHERE id = %s",
            (user_id,),
        ).fetchone()
        if not target_row:
            raise HTTPException(status_code=404, detail="User not found")

        current_role = _normalize_role(target_row[1])

        if actor.role != "owner" and target_role == "owner":
            raise HTTPException(status_code=403, detail="Only owners can assign owner role")
        if actor.role != "owner" and current_role == "owner":
            raise HTTPException(status_code=403, detail="Only owners can modify owners")
        if actor.role == "admin" and target_role == "admin":
            raise HTTPException(status_code=403, detail="Admins cannot assign admin role")

        if actor.role != "owner" and ROLE_WEIGHT[target_role] >= ROLE_WEIGHT[actor.role]:
            raise HTTPException(status_code=403, detail="Cannot assign equal or higher role")

        if current_role == "owner" and target_role != "owner":
            owner_count = _get_owner_count(conn)
            if owner_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last owner")

        conn.execute(
            "UPDATE \"user\" SET role = %s WHERE id = %s",
            (target_role, user_id),
        )
        conn.commit()

        updated = conn.execute(
            """
            SELECT id, name, email, role, COALESCE(banned, FALSE), "banReason", "createdAt", "banExpires"
            FROM "user"
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()
        return _to_user_info(updated)


@router.put("/users/{user_id}/ban")
def update_user_ban(
    user_id: str,
    req: UpdateUserBanRequest,
    actor: AuthUser = Depends(require_moderator),
):
    if actor.id == user_id and req.banned:
        raise HTTPException(status_code=400, detail="You cannot ban yourself")

    with get_conn() as conn:
        target_row = conn.execute(
            "SELECT id, role FROM \"user\" WHERE id = %s",
            (user_id,),
        ).fetchone()
        if not target_row:
            raise HTTPException(status_code=404, detail="User not found")

        target_role = _normalize_role(target_row[1])
        if actor.role != "owner" and ROLE_WEIGHT[target_role] >= ROLE_WEIGHT[actor.role]:
            raise HTTPException(status_code=403, detail="Cannot ban equal or higher role")

        if req.banned:
            conn.execute(
                """
                UPDATE "user"
                SET banned = TRUE,
                    "banReason" = %s,
                    "banExpires" = NULL
                WHERE id = %s
                """,
                (req.reason, user_id),
            )
            conn.execute('DELETE FROM session WHERE "userId" = %s', (user_id,))
        else:
            conn.execute(
                """
                UPDATE "user"
                SET banned = FALSE,
                    "banReason" = NULL,
                    "banExpires" = NULL
                WHERE id = %s
                """,
                (user_id,),
            )

        conn.commit()

        updated = conn.execute(
            """
            SELECT id, name, email, role, COALESCE(banned, FALSE), "banReason", "createdAt", "banExpires"
            FROM "user"
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()
        return _to_user_info(updated)
