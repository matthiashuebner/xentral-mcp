"""
SQLite persistence for the embedded authorization server.

Why not an in-process dict: the README tells operators to run this under
gunicorn, i.e. with several worker processes. An authorization code is minted by
whichever worker renders the consent form and redeemed by whichever worker
happens to receive `POST /oauth/token` — with per-process state that redemption
fails most of the time, and the failure looks exactly like the authorization
error we are trying to remove. sqlite3 is in the standard library, so this costs
no new dependency.

Codes, refresh tokens and client secrets are stored as SHA-256 hashes only. The
store file sits next to the process on disk; if it leaks it must not hand the
finder a set of live credentials.
"""

import hashlib
import hmac
import logging
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    client_id                  TEXT PRIMARY KEY,
    client_secret_hash         TEXT,
    client_name                TEXT NOT NULL,
    redirect_uris              TEXT NOT NULL,
    grant_types                TEXT NOT NULL,
    response_types             TEXT NOT NULL,
    token_endpoint_auth_method TEXT NOT NULL,
    scope                      TEXT NOT NULL,
    created_at                 INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_codes (
    code_hash      TEXT PRIMARY KEY,
    client_id      TEXT NOT NULL,
    redirect_uri   TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    scope          TEXT NOT NULL,
    resource       TEXT NOT NULL,
    expires_at     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    scope      TEXT NOT NULL,
    resource   TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS consent_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consent_failures_ip_at ON consent_failures(ip, at);
"""

_SIGNING_KEY_ROW = "signing_key"


def _now() -> int:
    return int(time.time())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OAuthStore:
    """Small synchronous store for clients, authorization codes and refresh tokens."""

    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        # isolation_level=None: autocommit, so the explicit BEGIN IMMEDIATE in
        # the single-use redemption paths is the only transaction in play.
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Signing key
    # ------------------------------------------------------------------

    def signing_key(self) -> bytes:
        """
        Return the token signing key, generating and persisting one on first
        call. Persisting it means tokens survive a restart, and every gunicorn
        worker signs and verifies with the same key without any configuration.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_SIGNING_KEY_ROW,)
            ).fetchone()
            if row is not None:
                return bytes.fromhex(row["value"])

            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
                (_SIGNING_KEY_ROW, secrets.token_bytes(32).hex()),
            )
            # Re-read rather than trusting our own INSERT: a concurrent worker
            # may have won the race, and both must end up with the same key.
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_SIGNING_KEY_ROW,)
            ).fetchone()
            return bytes.fromhex(row["value"])

    # ------------------------------------------------------------------
    # Clients (RFC 7591 dynamic registration)
    # ------------------------------------------------------------------

    def count_clients(self) -> int:
        with self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"])

    def register_client(
        self,
        *,
        client_name: str,
        redirect_uris: List[str],
        grant_types: List[str],
        response_types: List[str],
        token_endpoint_auth_method: str,
        scope: str,
    ) -> Dict[str, Any]:
        """Create a client record. Returns the record plus the plaintext secret (if any)."""
        client_id = f"mcp-{secrets.token_urlsafe(18)}"
        client_secret = (
            None
            if token_endpoint_auth_method == "none"
            else secrets.token_urlsafe(32)
        )

        record = {
            "client_id": client_id,
            "client_secret_hash": _hash(client_secret) if client_secret else None,
            "client_name": client_name,
            "redirect_uris": "\n".join(redirect_uris),
            "grant_types": " ".join(grant_types),
            "response_types": " ".join(response_types),
            "token_endpoint_auth_method": token_endpoint_auth_method,
            "scope": scope,
            "created_at": _now(),
        }

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO clients (client_id, client_secret_hash, client_name, "
                "redirect_uris, grant_types, response_types, "
                "token_endpoint_auth_method, scope, created_at) "
                "VALUES (:client_id, :client_secret_hash, :client_name, "
                ":redirect_uris, :grant_types, :response_types, "
                ":token_endpoint_auth_method, :scope, :created_at)",
                record,
            )

        result = self._row_to_client(record)
        result["client_secret"] = client_secret
        return result

    def find_public_client(
        self, client_name: str, redirect_uris: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Find an existing secret-less client with identical metadata.

        A remote client that retries a failed connection re-registers each time.
        Returning the existing record for byte-identical public-client metadata
        keeps a connect/disconnect loop from growing the table without bound.
        Confidential clients are never deduplicated — each needs its own secret.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE client_name = ? AND redirect_uris = ? "
                "AND token_endpoint_auth_method = 'none' ORDER BY created_at DESC LIMIT 1",
                (client_name, "\n".join(redirect_uris)),
            ).fetchone()
        return self._row_to_client(row) if row is not None else None

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        return self._row_to_client(row) if row is not None else None

    def verify_client_secret(self, client: Dict[str, Any], presented: str) -> bool:
        expected = client.get("client_secret_hash")
        if not expected:
            return False
        return hmac.compare_digest(_hash(presented), expected)

    @staticmethod
    def _row_to_client(row: Any) -> Dict[str, Any]:
        return {
            "client_id": row["client_id"],
            "client_secret_hash": row["client_secret_hash"],
            "client_name": row["client_name"],
            "redirect_uris": [u for u in row["redirect_uris"].split("\n") if u],
            "grant_types": row["grant_types"].split(),
            "response_types": row["response_types"].split(),
            "token_endpoint_auth_method": row["token_endpoint_auth_method"],
            "scope": row["scope"],
            "created_at": row["created_at"],
        }

    # ------------------------------------------------------------------
    # Authorization codes (single use)
    # ------------------------------------------------------------------

    def store_auth_code(
        self,
        code: str,
        *,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        scope: str,
        resource: str,
        ttl_seconds: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO auth_codes (code_hash, client_id, redirect_uri, "
                "code_challenge, scope, resource, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _hash(code),
                    client_id,
                    redirect_uri,
                    code_challenge,
                    scope,
                    resource,
                    _now() + ttl_seconds,
                ),
            )

    def consume_auth_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Redeem an authorization code exactly once.

        The SELECT and DELETE run inside one BEGIN IMMEDIATE so two concurrent
        redemptions of the same code cannot both succeed — replaying a stolen
        code after the legitimate exchange must fail.
        """
        code_hash = _hash(code)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM auth_codes WHERE code_hash = ?", (code_hash,)
                ).fetchone()
                if row is None:
                    return None
                conn.execute("DELETE FROM auth_codes WHERE code_hash = ?", (code_hash,))
            finally:
                conn.execute("COMMIT")

        if row["expires_at"] <= _now():
            return None

        return {
            "client_id": row["client_id"],
            "redirect_uri": row["redirect_uri"],
            "code_challenge": row["code_challenge"],
            "scope": row["scope"],
            "resource": row["resource"],
        }

    # ------------------------------------------------------------------
    # Refresh tokens (rotating, single use)
    # ------------------------------------------------------------------

    def store_refresh_token(
        self,
        token: str,
        *,
        client_id: str,
        scope: str,
        resource: str,
        ttl_seconds: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO refresh_tokens (token_hash, client_id, scope, resource, "
                "expires_at) VALUES (?, ?, ?, ?, ?)",
                (_hash(token), client_id, scope, resource, _now() + ttl_seconds),
            )

    def consume_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Redeem a refresh token exactly once (rotation on every use)."""
        token_hash = _hash(token)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
                ).fetchone()
                if row is None:
                    return None
                conn.execute(
                    "DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
                )
            finally:
                conn.execute("COMMIT")

        if row["expires_at"] <= _now():
            return None

        return {
            "client_id": row["client_id"],
            "scope": row["scope"],
            "resource": row["resource"],
        }

    def revoke_refresh_token(self, token: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM refresh_tokens WHERE token_hash = ?", (_hash(token),)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Consent brute-force throttle
    # ------------------------------------------------------------------

    def record_consent_failure(self, ip: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO consent_failures (ip, at) VALUES (?, ?)", (ip, _now())
            )

    def count_consent_failures(self, ip: str, window_seconds: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM consent_failures WHERE ip = ? AND at >= ?",
                (ip, _now() - window_seconds),
            ).fetchone()
        return int(row["n"])

    def clear_consent_failures(self, ip: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM consent_failures WHERE ip = ?", (ip,))

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def purge_expired(self, *, consent_window_seconds: int = 86400) -> None:
        """Drop expired codes/tokens and stale throttle rows. Best effort."""
        now = _now()
        try:
            with self._conn() as conn:
                conn.execute("DELETE FROM auth_codes WHERE expires_at <= ?", (now,))
                conn.execute("DELETE FROM refresh_tokens WHERE expires_at <= ?", (now,))
                conn.execute(
                    "DELETE FROM consent_failures WHERE at < ?",
                    (now - consent_window_seconds,),
                )
        except sqlite3.Error as exc:
            logger.warning("OAuth store housekeeping failed: %s", exc)
