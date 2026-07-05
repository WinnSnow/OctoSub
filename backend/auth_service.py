# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import time

from config import ADMIN_PASSWORD, ADMIN_PASSWORD_HASH, ADMIN_USERNAME, AUTH_SECRET, AUTH_TTL_SECONDS


def password_matches(password: str) -> bool:
    if ADMIN_PASSWORD_HASH:
        parts = ADMIN_PASSWORD_HASH.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            _, iterations, salt, expected = parts
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            )
            actual = base64.b64encode(digest).decode("ascii")
            return hmac.compare_digest(actual, expected)
        return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), ADMIN_PASSWORD_HASH)
    return bool(ADMIN_PASSWORD) and hmac.compare_digest(password, ADMIN_PASSWORD)


def sign_auth_payload(payload: str) -> str:
    return hmac.new(AUTH_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_auth_token(username: str) -> str:
    payload = json.dumps({"u": username, "exp": int(time.time()) + AUTH_TTL_SECONDS}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{encoded}.{sign_auth_payload(encoded)}"


def verify_auth_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(sign_auth_payload(encoded), signature):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    if payload.get("u") != ADMIN_USERNAME:
        return None
    return payload
