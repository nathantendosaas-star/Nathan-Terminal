"""Persistent Web Push subscriptions and delivery for the single-owner terminal."""
from __future__ import annotations
import hashlib, json, os, sqlite3
from datetime import datetime, timezone
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat
from pywebpush import WebPushException, webpush
from app.trading.router import _connect as _trading_connect

def _b64url(value: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

def _connect() -> sqlite3.Connection:
    conn = _trading_connect()
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS push_subscriptions (
      endpoint_hash TEXT PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE, p256dh TEXT NOT NULL,
      auth TEXT NOT NULL, device_name TEXT NOT NULL DEFAULT 'This device',
      created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS monitoring_push_deliveries (
      event_id INTEGER NOT NULL, endpoint_hash TEXT NOT NULL, status TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, delivered_at TEXT,
      PRIMARY KEY(event_id, endpoint_hash))""")
    conn.commit()
    return conn

def vapid_credentials() -> tuple[str, str]:
    with _connect() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute(
            "SELECT key,value FROM app_settings WHERE key IN ('webpush_vapid_private','webpush_vapid_public')"
        ).fetchall()}
        if rows.get("webpush_vapid_private") and rows.get("webpush_vapid_public"):
            return rows["webpush_vapid_public"], rows["webpush_vapid_private"]
        key = ec.generate_private_key(ec.SECP256R1())
        private_pem = key.private_bytes(serialization.Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("ascii")
        numbers = key.public_key().public_numbers()
        public_key = _b64url(b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big"))
        conn.execute("INSERT INTO app_settings(key,value) VALUES('webpush_vapid_private',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (private_pem,))
        conn.execute("INSERT INTO app_settings(key,value) VALUES('webpush_vapid_public',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (public_key,))
        conn.commit()
        return public_key, private_pem

def subscription_count() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0])

def save_subscription(endpoint: str, p256dh: str, auth: str, device_name: str = "This device") -> int:
    now = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(endpoint.encode()).hexdigest()
    with _connect() as conn:
        conn.execute("""INSERT INTO push_subscriptions(endpoint_hash,endpoint,p256dh,auth,device_name,created_at,last_seen_at)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(endpoint_hash) DO UPDATE SET endpoint=excluded.endpoint,
          p256dh=excluded.p256dh,auth=excluded.auth,device_name=excluded.device_name,last_seen_at=excluded.last_seen_at""",
          (digest, endpoint, p256dh, auth, device_name[:80], now, now))
        conn.commit()
        return int(conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0])

def remove_subscription(endpoint: str) -> int:
    digest = hashlib.sha256(endpoint.encode()).hexdigest()
    with _connect() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint_hash=?", (digest,))
        conn.commit()
        return int(conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0])

def deliver_monitoring_event(conn: sqlite3.Connection, event_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Monitoring event not found.")
    event = dict(row)
    subscriptions = conn.execute("SELECT * FROM push_subscriptions ORDER BY created_at").fetchall()
    if not subscriptions:
        conn.execute("UPDATE monitoring_events SET delivery_status='not_configured',last_error=? WHERE id=?",
                     ("No device has enabled phone notifications.", event_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone())
    _, private_key = vapid_credentials()
    payload = json.dumps({
        "title": "Nathan Terminal alert",
        "body": f"{event['event_type'].replace('_', ' ')} · {event['symbol']} · Trade #{event['trade_id']} · Review manually",
        "tag": f"nathan-terminal-event-{event_id}", "url": "/", "event_id": event_id,
    }, separators=(",", ":"))
    failures: list[str] = []
    active = delivered = 0
    attempted = False
    now = datetime.now(timezone.utc).isoformat()
    for item in subscriptions:
        sub = dict(item)
        previous = conn.execute("SELECT status,attempts FROM monitoring_push_deliveries WHERE event_id=? AND endpoint_hash=?",
                                (event_id, sub["endpoint_hash"])).fetchone()
        if previous and previous["status"] == "delivered":
            delivered += 1
            active += 1
            continue
        attempts = int(previous["attempts"]) if previous else 0
        if attempts >= 5:
            active += 1
            failures.append(f"{sub['device_name']}: retry limit reached")
            continue
        attempted = True
        error = None
        status = "delivered"
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=payload, vapid_private_key=private_key,
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")}, ttl=3600,
            )
            delivered += 1
            active += 1
        except WebPushException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            error = f"Push provider returned HTTP {code}." if code else "Push provider rejected the notification."
            status = "expired" if code in (404, 410) else "failed"
            failures.append(f"{sub['device_name']}: {error}")
            if status == "expired":
                conn.execute("DELETE FROM push_subscriptions WHERE endpoint_hash=?", (sub["endpoint_hash"],))
            else:
                active += 1
        except Exception as exc:
            status = "failed"
            error = f"Push delivery failed: {type(exc).__name__}"
            failures.append(f"{sub['device_name']}: {error}")
            active += 1
        conn.execute("""INSERT INTO monitoring_push_deliveries(event_id,endpoint_hash,status,attempts,last_error,delivered_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(event_id,endpoint_hash) DO UPDATE SET status=excluded.status,
          attempts=excluded.attempts,last_error=excluded.last_error,delivered_at=excluded.delivered_at""",
          (event_id, sub["endpoint_hash"], status, attempts + 1, error, now if status == "delivered" else None))
    overall = "not_configured" if active == 0 and delivered == 0 else ("failed" if failures else "delivered")
    old_attempts = int(event.get("delivery_attempts") or 0)
    conn.execute("""UPDATE monitoring_events SET delivery_status=?,delivery_attempts=?,last_error=?,delivered_at=? WHERE id=?""",
                 (overall, old_attempts + (1 if attempted else 0), "; ".join(failures)[:1000] or None,
                  now if overall == "delivered" else None, event_id))
    conn.commit()
    return dict(conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone())
