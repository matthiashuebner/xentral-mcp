"""
Token minting and verification for the embedded authorization server.

Access tokens are compact HS256 JWTs. They are deliberately *stateless*: the
MCP hot path (`POST /mcp`) validates them with one HMAC comparison and no
database read, so adding OAuth does not put a storage round-trip in front of
every tool call. The trade-off is that an access token cannot be revoked before
it expires — hence the short default TTL (1h) and revocable refresh tokens,
which are stored (hashed) in the SQLite store.

The same HMAC envelope is reused, with a distinct type tag, to sign the pending
authorization request that travels through the consent form as a hidden field.
The tags keep the two uses from ever being interchangeable.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Iterable, Optional


class TokenError(Exception):
    """Raised when a token or signed payload fails verification."""


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise TokenError(f"malformed base64url segment: {exc}")


def _sign(key: bytes, signing_input: bytes) -> str:
    return _b64u_encode(hmac.new(key, signing_input, hashlib.sha256).digest())


def pkce_s256_challenge(verifier: str) -> str:
    """Return the S256 code challenge for a PKCE verifier (RFC 7636)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64u_encode(digest)


# ---------------------------------------------------------------------------
# Access tokens
# ---------------------------------------------------------------------------

def issue_access_token(
    signing_key: bytes,
    *,
    issuer: str,
    subject: str,
    client_id: str,
    audience: str,
    scope: str,
    ttl_seconds: int,
    now: Optional[int] = None,
) -> tuple[str, int]:
    """
    Mint an access token. Returns (token, expires_in_seconds).

    `audience` carries the resource the token is good for (RFC 8707); the
    resource server refuses tokens minted for anything else, so a token
    phished by another MCP server cannot be replayed here.
    """
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + ttl_seconds

    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "client_id": client_id,
        "scope": scope,
        "iat": issued_at,
        "exp": expires_at,
        "jti": _b64u_encode(hashlib.sha256(
            f"{client_id}:{issued_at}:{expires_at}".encode()
        ).digest()[:12]),
    }

    segments = [
        _b64u_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64u_encode(json.dumps(claims, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    segments.append(_sign(signing_key, signing_input))

    return ".".join(segments), ttl_seconds


def verify_access_token(
    token: str,
    signing_key: bytes,
    *,
    issuer: str,
    audiences: Iterable[str],
    now: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Verify an access token and return its claims.

    Raises TokenError on any failure. The signature is checked before any claim
    is trusted, and compared with hmac.compare_digest to avoid a timing oracle.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("token must have three segments")

    header_segment, claims_segment, signature = parts
    signing_input = f"{header_segment}.{claims_segment}".encode("ascii")
    expected = _sign(signing_key, signing_input)
    if not hmac.compare_digest(signature, expected):
        raise TokenError("signature mismatch")

    try:
        header = json.loads(_b64u_decode(header_segment))
        claims = json.loads(_b64u_decode(claims_segment))
    except (ValueError, TypeError) as exc:
        raise TokenError(f"malformed token payload: {exc}")

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise TokenError("unexpected token algorithm")
    if not isinstance(claims, dict):
        raise TokenError("token claims must be an object")

    if claims.get("iss") != issuer:
        raise TokenError("issuer mismatch")

    token_audience = claims.get("aud")
    accepted = {a.rstrip("/") for a in audiences}
    presented = (
        {str(a).rstrip("/") for a in token_audience}
        if isinstance(token_audience, list)
        else {str(token_audience).rstrip("/")}
    )
    if not presented & accepted:
        raise TokenError("audience mismatch")

    current = int(time.time()) if now is None else now
    expires_at = claims.get("exp")
    if not isinstance(expires_at, int) or current >= expires_at:
        raise TokenError("token expired")

    return claims


# ---------------------------------------------------------------------------
# Generic signed payloads (consent form round-trip)
# ---------------------------------------------------------------------------

def sign_payload(
    signing_key: bytes,
    payload: Dict[str, Any],
    *,
    purpose: str,
    ttl_seconds: int,
    now: Optional[int] = None,
) -> str:
    """
    Sign a short-lived payload so it can travel through an untrusted round-trip
    (a hidden form field) and come back unmodified.
    """
    issued_at = int(time.time()) if now is None else now
    envelope = {
        "p": purpose,
        "exp": issued_at + ttl_seconds,
        "d": payload,
    }
    body = _b64u_encode(json.dumps(envelope, separators=(",", ":")).encode())
    return f"{body}.{_sign(signing_key, body.encode('ascii'))}"


def verify_payload(
    blob: str,
    signing_key: bytes,
    *,
    purpose: str,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    """Verify a payload produced by sign_payload and return its data."""
    parts = blob.split(".")
    if len(parts) != 2:
        raise TokenError("signed payload must have two segments")

    body, signature = parts
    if not hmac.compare_digest(signature, _sign(signing_key, body.encode("ascii"))):
        raise TokenError("signed payload signature mismatch")

    try:
        envelope = json.loads(_b64u_decode(body))
    except (ValueError, TypeError) as exc:
        raise TokenError(f"malformed signed payload: {exc}")

    if not isinstance(envelope, dict):
        raise TokenError("signed payload must be an object")
    if envelope.get("p") != purpose:
        raise TokenError("signed payload purpose mismatch")

    expires_at = envelope.get("exp")
    current = int(time.time()) if now is None else now
    if not isinstance(expires_at, int) or current >= expires_at:
        raise TokenError("signed payload expired")

    data = envelope.get("d")
    if not isinstance(data, dict):
        raise TokenError("signed payload data must be an object")
    return data
