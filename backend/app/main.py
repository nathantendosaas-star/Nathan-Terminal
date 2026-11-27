from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Nathan Terminal API", version="0.1.0", description="Personal market intelligence and decision-support API.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ServiceStatus(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime
    market_data: str

@app.get("/health", response_model=ServiceStatus)
async def health() -> ServiceStatus:
    return ServiceStatus(status="ok", service="nathan-terminal-api", version=app.version, timestamp=datetime.now(timezone.utc), market_data="not_configured")

@app.get("/api/v1/overview")
async def overview() -> dict[str, str]:
    return {"mode": "research_only", "market_data": "not_configured", "forecast_model": "not_configured", "message": "Connect a verified market-data provider before displaying live prices."}
