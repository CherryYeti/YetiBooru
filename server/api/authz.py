from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote

from fastapi import Depends, HTTPException, Request

from api.db import get_conn, sync_bootstrap_owner_roles

Role = Literal["owner", "admin", "moderator", "user"]

ROLE_WEIGHT: dict[str, int] = {
    "user": 1,
    "moderator": 2,
    "admin": 3,
    "owner": 4,
}

SESSION_TOKEN_COOKIE_NAMES = (
    "better-auth.session_token",
    "__Secure-better-auth.session_token",
    "__Host-better-auth.session_token",
    "session_token",
)


@dataclass
class AuthUser:
    id: str
    name: str
    email: str
    role: Role
    banned: bool


def _normalize_role(raw_role: str | None) -> Role:
    role = (raw_role or "user").strip().lower()
    if role == "mod":
        role = "moderator"
    if role not in ROLE_WEIGHT:
        role = "user"
    return role  # type: ignore[return-value]


def _extract_session_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    for cookie_name in SESSION_TOKEN_COOKIE_NAMES:
        token = request.cookies.get(cookie_name)
        if token:
            return token

    return None


def _token_candidates(raw_token: str | None) -> list[str]:
    if not raw_token:
        return []

    candidates: list[str] = []

    def _add(value: str | None) -> None:
        if not value:
            return
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    _add(raw_token)
    _add(unquote(raw_token))

    for token in list(candidates):
        if "." in token:
            _add(token.split(".", 1)[0])
        if ":" in token:
            _add(token.split(":", 1)[0])
        if "|" in token:
            _add(token.split("|", 1)[0])

    return candidates


def _get_user_from_request(request: Request) -> AuthUser | None:
    token = _extract_session_token(request)
    token_candidates = _token_candidates(token)

    if not token_candidates:
        for cookie_name, cookie_value in request.cookies.items():
            lowered = cookie_name.lower()
            if lowered.endswith("session_token") or lowered.endswith("session-token"):
                token_candidates.extend(_token_candidates(cookie_value))

    if not token_candidates:
        return None

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.role, COALESCE(u.banned, FALSE)
            FROM session s
            JOIN "user" u ON u.id = s."userId"
            WHERE (s.token = ANY(%s::text[]) OR s.id = ANY(%s::text[]))
              AND s."expiresAt" > CURRENT_TIMESTAMP
            LIMIT 1
            """,
            (token_candidates, token_candidates),
        ).fetchone()

        if row:
            sync_bootstrap_owner_roles(conn, row[2])
            row = conn.execute(
                """
                SELECT u.id, u.name, u.email, u.role, COALESCE(u.banned, FALSE)
                FROM session s
                JOIN "user" u ON u.id = s."userId"
                WHERE (s.token = ANY(%s::text[]) OR s.id = ANY(%s::text[]))
                  AND s."expiresAt" > CURRENT_TIMESTAMP
                LIMIT 1
                """,
                (token_candidates, token_candidates),
            ).fetchone()

    if not row:
        return None

    return AuthUser(
        id=row[0],
        name=row[1],
        email=row[2],
        role=_normalize_role(row[3]),
        banned=bool(row[4]),
    )


def get_current_user_optional(request: Request) -> AuthUser | None:
    return _get_user_from_request(request)


def require_user(request: Request) -> AuthUser:
    user = _get_user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.banned:
        raise HTTPException(status_code=403, detail="Account is banned")
    return user


def require_min_role(min_role: Role):
    min_weight = ROLE_WEIGHT[min_role]

    def _dependency(user: AuthUser = Depends(require_user)) -> AuthUser:
        if ROLE_WEIGHT[user.role] < min_weight:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dependency


require_moderator = require_min_role("moderator")
require_admin = require_min_role("admin")
require_owner = require_min_role("owner")
