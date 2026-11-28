"""Single-owner password login with short-lived signed bearer sessions."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time
from collections import defaultdict, deque
from threading import Lock
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
TOKEN_TTL_SECONDS = 12 * 60 * 60
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = Lock()

class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return "scrypt${}${}${}${}${}".format(n, r, p, _b64(salt), _b64(digest))

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt": return False
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(_unb64(expected)))
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError, MemoryError): return False

def issue_token() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret) < 32: raise HTTPException(status_code=503, detail="Authentication secret is not configured. Set AUTH_SECRET_KEY.")
    payload = _b64(json.dumps({"exp": int(time.time()) + TOKEN_TTL_SECONDS}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return "{}.{}".format(payload, signature)

def token_is_valid(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
        secret = os.getenv("AUTH_SECRET_KEY", "")
        if len(secret) < 32: return False
        expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected): return False
        return int(json.loads(_unb64(payload)).get("exp", 0)) > int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError): return False

def _allow_attempt(ip: str) -> bool:
    now = time.monotonic()
    with _attempts_lock:
        attempts = _attempts[ip]
        while attempts and now - attempts[0] > 900: attempts.popleft()
        if len(attempts) >= 8: return False
        attempts.append(now)
        return True

@router.get("/status")
def auth_status(request: Request):
    configured = bool(os.getenv("APP_PASSWORD_HASH"))
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    return {"auth_required": configured, "authenticated": bool(configured and token and token_is_valid(token)), "session_expires_in": TOKEN_TTL_SECONDS}

@router.post("/login")
def login(body: LoginRequest, request: Request):
    encoded = os.getenv("APP_PASSWORD_HASH", "")
    if not encoded: raise HTTPException(status_code=503, detail="Set APP_PASSWORD_HASH on the backend to enable password protection.")
    ip = request.client.host if request.client else "unknown"
    if not _allow_attempt(ip): raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")
    if not verify_password(body.password, encoded): raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"access_token": issue_token(), "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS}

@router.post("/logout")
def logout():
    return {"ok": True}
