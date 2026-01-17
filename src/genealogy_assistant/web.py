"""
FastAPI web service for the Genealogy Research Assistant.

Provides REST API endpoints for GPS-compliant genealogy research.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from genealogy_assistant.api.assistant import GenealogyAssistant, AssistantConfig
from genealogy_assistant.core.gedcom import GedcomManager
from genealogy_assistant.core.models import ConfidenceLevel
from genealogy_assistant.search.unified import UnifiedSearch, UnifiedSearchConfig
from genealogy_assistant.adapters.gramps_web.api import router as smart_search_router


# =============================================================================
# Application Lifespan
# =============================================================================

# Global instances
_assistant: GenealogyAssistant | None = None
_search: UnifiedSearch | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global _assistant, _search

    # Startup
    config = AssistantConfig()
    _assistant = GenealogyAssistant(config)
    await _assistant.connect()

    _search = UnifiedSearch()
    await _search.connect()

    yield

    # Shutdown
    if _assistant:
        await _assistant.close()
    if _search:
        await _search.close()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Genealogy Research Assistant API",
    description="GPS-compliant AI-powered genealogy research following BCG certification standards.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Smart Search Router
app.include_router(smart_search_router, prefix="/api")


# =============================================================================
# Request/Response Models
# =============================================================================

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str


class ResearchRequest(BaseModel):
    question: str = Field(..., description="Genealogical research question")
    context: dict[str, Any] | None = Field(None, description="Additional context")


class ResearchResponse(BaseModel):
    message: str
    confidence: str
    next_actions: list[str]
    ai_assisted: bool


class SearchRequest(BaseModel):
    surname: str = Field(..., description="Surname to search")
    given_name: str | None = Field(None, description="Given name")
    birth_year: int | None = Field(None, description="Approximate birth year")
    birth_place: str | None = Field(None, description="Birth place")
    providers: list[str] | None = Field(None, description="Specific providers to search")


class SearchResult(BaseModel):
    given_name: str
    surname: str
    birth_date: str | None
    death_date: str | None
    birth_place: str | None
    provider: str
    source_level: str
    url: str | None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total_count: int
    providers_searched: list[str]
    providers_failed: list[str]
    search_time_ms: float


class PersonTarget(BaseModel):
    surname: str
    given_name: str | None = None
    birth_year: int | None = None
    birth_place: str | None = None


class ResearchPlanRequest(BaseModel):
    target: PersonTarget
    goal: str = Field(..., description="Research goal")


class VerifyRequest(BaseModel):
    conclusion: str = Field(..., description="Genealogical conclusion to verify")
    evidence: list[str] = Field(..., description="Evidence supporting conclusion")


class LetterRequest(BaseModel):
    archive: str = Field(..., description="Target archive/repository")
    person_name: str = Field(..., description="Person being researched")
    records_needed: list[str] = Field(..., description="Records to request")
    known_facts: list[str] = Field(default_factory=list, description="Known facts")


class LetterResponse(BaseModel):
    letter: str


class GedcomStats(BaseModel):
    individuals: int
    families: int
    sources: int
    notes: int
    version: str | None


class GedcomValidation(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class PersonResult(BaseModel):
    id: str
    name: str
    birth: str | None
    death: str | None


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Check if API is ready to serve requests."""
    if _assistant is None or _search is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return {"status": "ready"}


# =============================================================================
# Research Endpoints
# =============================================================================

@app.post("/research/ask", response_model=ResearchResponse, tags=["Research"])
async def research_ask(request: ResearchRequest):
    """
    Ask a genealogical research question.

    Uses AI to provide GPS-compliant research guidance with proper
    source hierarchy and evidence analysis.
    """
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    response = await _assistant.research(request.question, request.context)

    return ResearchResponse(
        message=response.message,
        confidence=response.confidence.value,
        next_actions=response.next_actions,
        ai_assisted=response.ai_assisted,
    )


@app.post("/research/plan", response_model=ResearchResponse, tags=["Research"])
async def research_plan(request: ResearchPlanRequest):
    """
    Create a GPS-compliant research plan.

    Generates systematic research steps prioritizing primary sources.
    """
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    from genealogy_assistant.core.models import Person, PersonName, Event, GenealogyDate, Place

    # Build target person
    target = Person(id="target")
    target.primary_name = PersonName(
        surname=request.target.surname,
        given=request.target.given_name or "",
    )

    if request.target.birth_year or request.target.birth_place:
        target.birth = Event(event_type="BIRT")
        if request.target.birth_year:
            target.birth.date = GenealogyDate(year=request.target.birth_year)
        if request.target.birth_place:
            target.birth.place = Place(name=request.target.birth_place)

    response = await _assistant.create_research_plan(target, request.goal)

    return ResearchResponse(
        message=response.message,
        confidence=response.confidence.value,
        next_actions=response.next_actions,
        ai_assisted=response.ai_assisted,
    )


@app.post("/research/verify", response_model=ResearchResponse, tags=["Research"])
async def research_verify(request: VerifyRequest):
    """
    Verify a genealogical conclusion against GPS standards.

    Evaluates whether the evidence supports the conclusion.
    """
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    response = await _assistant.verify_conclusion(request.conclusion, request.evidence)

    return ResearchResponse(
        message=response.message,
        confidence=response.confidence.value,
        next_actions=response.next_actions,
        ai_assisted=response.ai_assisted,
    )


@app.post("/research/letter", response_model=LetterResponse, tags=["Research"])
async def generate_letter(request: LetterRequest):
    """
    Generate a professional archive request letter.

    Creates a formal letter requesting genealogical records.
    """
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    letter = await _assistant.generate_archive_letter(
        archive=request.archive,
        person_name=request.person_name,
        records_needed=request.records_needed,
        known_facts=request.known_facts,
    )

    return LetterResponse(letter=letter)


@app.post("/research/reset", tags=["Research"])
async def reset_conversation():
    """Clear conversation history for fresh context."""
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    _assistant.reset_conversation()
    return {"status": "conversation reset"}


# =============================================================================
# Search Endpoints
# =============================================================================

@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_person(request: SearchRequest):
    """
    Search for a person across genealogy databases.

    Searches FamilySearch, Geneanet, Belgian Archives, and FindAGrave.
    """
    if _search is None:
        raise HTTPException(status_code=503, detail="Search not initialized")

    response = await _search.search_person(
        surname=request.surname,
        given_name=request.given_name,
        birth_year=request.birth_year,
        birth_place=request.birth_place,
        providers=request.providers,
    )

    results = []
    for r in response.results:
        results.append(SearchResult(
            given_name=r.given_name,
            surname=r.surname,
            birth_date=r.birth_date.to_gedcom() if r.birth_date else None,
            death_date=r.death_date.to_gedcom() if r.death_date else None,
            birth_place=r.birth_place.name if r.birth_place else None,
            provider=r.provider,
            source_level=r.source_level.value,
            url=r.url,
        ))

    return SearchResponse(
        results=results,
        total_count=response.total_count,
        providers_searched=response.providers_searched,
        providers_failed=response.providers_failed,
        search_time_ms=response.search_time_ms,
    )


@app.post("/search/analyze", response_model=ResearchResponse, tags=["Search"])
async def search_and_analyze(request: SearchRequest):
    """
    Search databases and analyze results with AI.

    Combines database search with GPS-compliant analysis.
    """
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    response = await _assistant.search_and_analyze(
        surname=request.surname,
        given_name=request.given_name,
        birth_year=request.birth_year,
        birth_place=request.birth_place,
        providers=request.providers,
    )

    return ResearchResponse(
        message=response.message,
        confidence=response.confidence.value,
        next_actions=response.next_actions,
        ai_assisted=response.ai_assisted,
    )


@app.get("/search/providers", tags=["Search"])
async def list_providers():
    """List available search providers."""
    if _search is None:
        raise HTTPException(status_code=503, detail="Search not initialized")

    return {"providers": _search.available_providers}


# =============================================================================
# GEDCOM Endpoints
# =============================================================================

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))


@app.post("/gedcom/upload", tags=["GEDCOM"])
async def upload_gedcom(file: UploadFile = File(...)):
    """
    Upload a GEDCOM file.

    Validates and stores the file for research.
    """
    if not file.filename or not file.filename.endswith((".ged", ".gedcom")):
        raise HTTPException(status_code=400, detail="File must be a GEDCOM file (.ged)")

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = DATA_DIR / file.filename
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # Validate
    manager = GedcomManager()
    try:
        manager.load(str(file_path))
        stats = manager.stats()
        issues = manager.validate()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GEDCOM file: {e}")

    return {
        "filename": file.filename,
        "stats": stats,
        "validation_issues": len(issues),
    }


@app.get("/gedcom/list", tags=["GEDCOM"])
async def list_gedcom_files():
    """List available GEDCOM files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for f in DATA_DIR.glob("*.ged"):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime),
        })

    return {"files": files}


@app.get("/gedcom/{filename}/stats", response_model=GedcomStats, tags=["GEDCOM"])
async def gedcom_stats(filename: str):
    """Get statistics for a GEDCOM file."""
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    manager = GedcomManager()
    manager.load(str(file_path))
    stats = manager.stats()

    return GedcomStats(
        individuals=stats.get("individuals", 0),
        families=stats.get("families", 0),
        sources=stats.get("sources", 0),
        notes=stats.get("notes", 0),
        version=stats.get("version"),
    )


@app.get("/gedcom/{filename}/validate", response_model=GedcomValidation, tags=["GEDCOM"])
async def validate_gedcom(filename: str):
    """Validate a GEDCOM file for GPS compliance."""
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    manager = GedcomManager()
    manager.load(str(file_path))
    issues = manager.validate()

    errors = [i for i in issues if i.startswith("ERROR")]
    warnings = [i for i in issues if i.startswith("WARNING")]

    return GedcomValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@app.get("/gedcom/{filename}/search", response_model=list[PersonResult], tags=["GEDCOM"])
async def search_gedcom(
    filename: str,
    surname: str | None = Query(None),
    given: str | None = Query(None),
):
    """Search for persons in a GEDCOM file."""
    if not surname and not given:
        raise HTTPException(status_code=400, detail="Provide surname or given name")

    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    manager = GedcomManager()
    manager.load(str(file_path))
    results = manager.find_persons(surname=surname, given_name=given)

    return [
        PersonResult(
            id=p.id,
            name=p.primary_name.full_name() if p.primary_name else "Unknown",
            birth=p.birth.date.to_gedcom() if p.birth and p.birth.date else None,
            death=p.death.date.to_gedcom() if p.death and p.death.date else None,
        )
        for p in results[:100]
    ]


@app.get("/gedcom/{filename}/download", tags=["GEDCOM"])
async def download_gedcom(filename: str):
    """Download a GEDCOM file."""
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/x-gedcom",
    )


# =============================================================================
# Gramps Integration Endpoints
# =============================================================================

@app.get("/gramps/status", tags=["Gramps"])
async def gramps_status():
    """Check Gramps Web connection status."""
    from genealogy_assistant.gramps.web_api import GrampsWebClient, GrampsWebConfig

    url = os.getenv("GRAMPS_WEB_URL", "http://gramps-web:5000")
    user = os.getenv("GRAMPS_WEB_USER")
    password = os.getenv("GRAMPS_WEB_PASS")

    config = GrampsWebConfig(base_url=url, username=user, password=password)

    try:
        async with GrampsWebClient(config) as client:
            await client.authenticate()
            metadata = await client.get_metadata()
            return {
                "connected": True,
                "url": url,
                "database": metadata.get("database", {}).get("name"),
            }
    except Exception as e:
        return {
            "connected": False,
            "url": url,
            "error": str(e),
        }


@app.get("/gramps/search", tags=["Gramps"])
async def gramps_search(query: str = Query(..., min_length=2)):
    """Search Gramps Web database."""
    from genealogy_assistant.gramps.web_api import GrampsWebClient, GrampsWebConfig

    url = os.getenv("GRAMPS_WEB_URL", "http://gramps-web:5000")
    user = os.getenv("GRAMPS_WEB_USER")
    password = os.getenv("GRAMPS_WEB_PASS")

    config = GrampsWebConfig(base_url=url, username=user, password=password)

    try:
        async with GrampsWebClient(config) as client:
            await client.authenticate()
            results = await client.search(query)
            return results
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gramps search failed: {e}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
