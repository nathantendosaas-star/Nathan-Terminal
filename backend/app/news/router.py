"""Read-only RSS news aggregation via Google News RSS."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/news", tags=["news"])
RSS_URL = "https://news.google.com/rss/search"


@router.get("")
async def get_news(
    q: str = Query(default="financial markets OR bitcoin OR stocks", min_length=2, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
):
    params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(RSS_URL, params=params, headers={"User-Agent": "NathanTerminal/1.0"})
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        raise HTTPException(status_code=502, detail="News provider is temporarily unavailable.") from exc

    items = []
    for item in root.findall("./channel/item")[:limit]:
        source = item.findtext("source") or "Unknown"
        published = item.findtext("pubDate")
        try:
            published_at = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat() if published else None
        except (TypeError, ValueError, OverflowError):
            published_at = None
        items.append({
            "title": item.findtext("title") or "Untitled",
            "url": item.findtext("link"),
            "source": source,
            "published_at": published_at,
            "summary": item.findtext("description") or "",
        })
    return {
        "query": q,
        "provider": "Google News RSS",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
        "disclaimer": "Headlines and summaries are provided for research context. Verify important information with the original publisher.",
    }
