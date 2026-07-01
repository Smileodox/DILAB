"""Standalone FastAPI server for Technology Drivers Identification."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tdi.config import get_settings
from tdi.models.output import TechnologyDriversIdentificationOutput
from tdi.models.schemas import QueryRequest
from tdi.pipeline import TechnologyDriversIdentificationPipeline

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Self-contained Technology Drivers Identification — RAG JSON export",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = TechnologyDriversIdentificationPipeline()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "technology_drivers_identification",
        "model": settings.llm_model,
    }


@app.post("/identify", response_model=TechnologyDriversIdentificationOutput)
async def identify(request: QueryRequest):
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY not configured. Copy .env.example to .env and set your key.",
        )
    try:
        return await pipeline.run(query=request.query, target_year=request.target_year)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="OpenRouter rate limit — wait and retry.")
        raise HTTPException(status_code=502, detail=f"LLM API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Identification failed: {str(e)}")
