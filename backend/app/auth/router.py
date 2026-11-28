"""Single-owner password setup/login with persistent signed bearer sessions."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, sqlite3, time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
router=APIRouter(prefix="/api/v1/auth",tags=["authentication"])
TOKEN_TTL_SECONDS=12*60*60
_attempts:dict[str,deque[float]]=defaultdict(deque)
_attempts_lock=Lock()
class PasswordRequest(BaseModel):
    password:str=Field(min_length=12,max_length=1024)
class LoginRequest(BaseModel):
    password:str=Field(min_length=1,max_length=1024)
def _db_path()->str:
    return os.getenv("AUTH_DB_PATH") or os.getenv("TRADING_DB_PATH") or str(Path(__file__).resolve().parents[2]/"data"/"trade_desk.sqlite3")
def _connect()->sqlite3.Connection:
    path=_db_path();Path(path).parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(path,timeout=15);connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return connection
def get_setting(key:str,default:str="")->str:
    with _connect() as connection: row=connection.execute("SELECT value FROM app_settings WHERE key=?",(key,)).fetchone()
    return str(row[0]) if row else default
def set_setting(key:str,value:str)->None:
    with _connect() as connection: connection.execute("INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value))
def _configured_password_hash()->str:
    return os.getenv("APP_PASSWORD_HASH","").strip() or get_setting("auth_password_hash")
def auth_is_configured()->bool:
    return bool(_configured_password_hash())
def _signing_secret(create:bool=False)->str:
    configured=os.getenv("AUTH_SECRET_KEY","").strip()
    if len(configured)>=32:return configured
    stored=get_setting("auth_signing_secret")
    if stored:return stored
    if not create:return ""
    generated=secrets.token_urlsafe(48);set_setting("auth_signing_secret",generated);return generated
def _b64(data:bytes)->str:return base64.urlsafe_b64encode(data).decode().rstrip("=")
def _unb64(value:str)->bytes:return base64.urlsafe_b64decode(value+"="*(-len(value)%4))
def hash_password(password:str)->str:
    salt=secrets.token_bytes(16);n,r,p=2**14,8,1
    digest=hashlib.scrypt(password.encode(),salt=salt,n=n,r=r,p=p,dklen=32)
    return "scrypt${}${}${}${}${}".format(n,r,p,_b64(salt),_b64(digest))
def verify_password(password:str,encoded:str)->bool:
    try:
        algorithm,n,r,p,salt,expected=encoded.split("$")
        if algorithm!="scrypt":return False
        actual=hashlib.scrypt(password.encode(),salt=_unb64(salt),n=int(n),r=int(r),p=int(p),dklen=len(_unb64(expected)))
        return hmac.compare_digest(actual,_unb64(expected))
    except (ValueError,TypeError,MemoryError):return False
def issue_token()->str:
    secret=_signing_secret(create=True)
    payload=_b64(json.dumps({"exp":int(time.time())+TOKEN_TTL_SECONDS},separators=(",",":")).encode())
    signature=_b64(hmac.new(secret.encode(),payload.encode(),hashlib.sha256).digest())
    return f"{payload}.{signature}"
def token_is_valid(token:str)->bool:
    try:
        payload,signature=token.split(".",1);secret=_signing_secret()
        if len(secret)<32:return False
        expected=_b64(hmac.new(secret.encode(),payload.encode(),hashlib.sha256).digest())
        return hmac.compare_digest(signature,expected) and int(json.loads(_unb64(payload)).get("exp",0))>int(time.time())
    except (ValueError,TypeError,json.JSONDecodeError):return False
def _allow_attempt(ip:str)->bool:
    now=time.monotonic()
    with _attempts_lock:
        attempts=_attempts[ip]
        while attempts and now-attempts[0]>900:attempts.popleft()
        if len(attempts)>=8:return False
        attempts.append(now);return True
@router.get("/status")
def auth_status(request:Request):
    configured=auth_is_configured();authorization=request.headers.get("authorization","")
    token=authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    return {"auth_required":configured,"setup_required":not configured,"authenticated":bool(configured and token and token_is_valid(token)),"session_expires_in":TOKEN_TTL_SECONDS}
@router.post("/setup")
def setup_password(body:PasswordRequest):
    connection=_connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing=connection.execute("SELECT value FROM app_settings WHERE key='auth_password_hash'").fetchone()
        if os.getenv("APP_PASSWORD_HASH","").strip() or existing:raise HTTPException(status_code=409,detail="Password setup has already been completed.")
        encoded=hash_password(body.password);secret=secrets.token_urlsafe(48)
        connection.execute("INSERT INTO app_settings(key,value) VALUES('auth_password_hash',?)",(encoded,))
        connection.execute("INSERT INTO app_settings(key,value) VALUES('auth_signing_secret',?)",(secret,))
        connection.commit()
    except Exception:connection.rollback();raise
    finally:connection.close()
    return {"access_token":issue_token(),"token_type":"bearer","expires_in":TOKEN_TTL_SECONDS}
@router.post("/login")
def login(body:LoginRequest,request:Request):
    encoded=_configured_password_hash()
    if not encoded:raise HTTPException(status_code=409,detail="Create your terminal password first.")
    ip=request.client.host if request.client else "unknown"
    if not _allow_attempt(ip):raise HTTPException(status_code=429,detail="Too many login attempts. Try again in 15 minutes.")
    if not verify_password(body.password,encoded):raise HTTPException(status_code=401,detail="Incorrect password.")
    return {"access_token":issue_token(),"token_type":"bearer","expires_in":TOKEN_TTL_SECONDS}
@router.post("/logout")
def logout():return {"ok":True}
