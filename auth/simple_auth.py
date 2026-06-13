from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


PBKDF2_ITERATIONS = 120_000


class AuthError(ValueError):
    pass


class SimpleAuthService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or get_settings().auth_db_path)

    def register(
        self,
        username: str,
        password: str,
        display_name: str | None = None,
        recipe_user_id: int | None = None,
    ) -> dict[str, Any]:
        username = _normalize_username(username)
        display_name = (display_name or username).strip()[:64]
        recipe_user_id = int(recipe_user_id or 1535)
        password_hash = _hash_password(password)
        created_at = datetime.now(timezone.utc).isoformat()

        self._ensure_schema()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO auth_users (username, password_hash, display_name, recipe_user_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (username, password_hash, display_name, recipe_user_id, created_at),
                )
                conn.commit()
                account_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthError("用户名已存在") from exc

        return {
            "account_id": account_id,
            "username": username,
            "display_name": display_name,
            "user_id": recipe_user_id,
            "recipe_user_id": recipe_user_id,
            "created_at": created_at,
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        username = _normalize_username(username)
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, username, password_hash, display_name, recipe_user_id, created_at
                FROM auth_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

        if row is None or not _verify_password(password, row["password_hash"]):
            raise AuthError("用户名或密码错误")

        recipe_user_id = int(row["recipe_user_id"])
        return {
            "account_id": int(row["id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"] or row["username"]),
            "user_id": recipe_user_id,
            "recipe_user_id": recipe_user_id,
            "created_at": str(row["created_at"]),
        }

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    recipe_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()


def _normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if len(normalized) < 3:
        raise AuthError("用户名至少需要 3 个字符")
    if not normalized.replace("_", "").replace("-", "").isalnum():
        raise AuthError("用户名只能包含字母、数字、短横线和下划线")
    return normalized


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False
