"""Authenticated Web Push subscription management endpoints."""
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.push.service import remove_subscription, save_subscription, subscription_count, vapid_credentials

router = APIRouter(prefix="/api/v1/push", tags=["push notifications"])

class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=256)
    auth: str = Field(min_length=8, max_length=128)

class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4096)
    keys: SubscriptionKeys
    device_name: str = Field(default="This device", min_length=1, max_length=80)

class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4096)

@router.get("/public-key")
def get_public_key():
    public_key, _ = vapid_credentials()
    return {"public_key": public_key}

@router.get("/status")
def push_status():
    count = subscription_count()
    return {"enabled": count > 0, "active_devices": count, "provider": "web_push"}

@router.post("/subscribe")
def subscribe(body: PushSubscriptionRequest):
    parsed = urlsplit(body.endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Push subscription endpoint must use HTTPS.")
    count = save_subscription(body.endpoint, body.keys.p256dh, body.keys.auth, body.device_name)
    return {"saved": True, "active_devices": count}

@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeRequest):
    count = remove_subscription(body.endpoint)
    return {"removed": True, "active_devices": count}
