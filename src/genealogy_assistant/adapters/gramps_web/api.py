"""FastAPI router for Smart Search integration with Gramps Web.

Provides REST endpoints for:
- Getting search recommendations for a person
- Querying the source registry
- Executing smart searches across providers
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from genealogy_assistant.core.models import SourceLevel
from genealogy_assistant.router import SmartRouter, SourceRecommendation, SourceRegistry


router = APIRouter(prefix="/smart-search", tags=["Smart Search"])


# Pydantic models for API
class PersonContext(BaseModel):
    """Person context for routing."""

    surname: str | None = None
    given_name: str | None = None
    birth_year: int | None = None
    birth_place: str | None = None
    death_year: int | None = None
    death_place: str | None = None
    ethnicities: list[str] = Field(default_factory=list)


class SourceInfo(BaseModel):
    """Source information."""

    id: str
    name: str
    description: str | None = None
    url: str | None = None
    source_level: str
    geographic: list[str] = Field(default_factory=list)
    record_types: list[str] = Field(default_factory=list)
    temporal_start: int | None = None
    temporal_end: int | None = None


class RecommendationResponse(BaseModel):
    """Search recommendation."""

    source_id: str
    source_name: str
    reason: str
    priority: int
    source_level: str
    url: str | None = None
    provider: str | None = None
    record_types: list[str] = Field(default_factory=list)
    search_params: dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool = False


class RouteRequest(BaseModel):
    """Request for routing recommendations."""

    person: PersonContext | None = None
    surname: str | None = None
    locations: list[str] = Field(default_factory=list)
    year: int | None = None
    ethnicities: list[str] = Field(default_factory=list)


class RouteResponse(BaseModel):
    """Response with routing recommendations."""

    recommendations: list[RecommendationResponse]
    total: int
    rule_based: int
    ai_generated: int


# Initialize router (singleton)
_registry: SourceRegistry | None = None
_router: SmartRouter | None = None


def get_registry() -> SourceRegistry:
    """Get or create source registry."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry


def get_router() -> SmartRouter:
    """Get or create smart router."""
    global _router
    if _router is None:
        _router = SmartRouter(registry=get_registry(), enable_ai_fallback=False)
    return _router


@router.get("/sources", response_model=list[SourceInfo])
async def list_sources(
    location: str | None = Query(None, description="Filter by location"),
    year: int | None = Query(None, description="Filter by year"),
    source_level: str | None = Query(None, description="Filter by source level"),
) -> list[SourceInfo]:
    """List all registered sources with optional filtering."""
    registry = get_registry()

    # Parse source level if provided
    level = None
    if source_level:
        try:
            level = SourceLevel(source_level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source level: {source_level}")

    sources = registry.find_sources(
        locations=[location] if location else None,
        year=year,
        source_level=level,
    )

    return [
        SourceInfo(
            id=s.id,
            name=s.name,
            description=s.description,
            url=s.url,
            source_level=s.source_level.value,
            geographic=s.geographic,
            record_types=s.record_types,
            temporal_start=s.temporal.start,
            temporal_end=s.temporal.end,
        )
        for s in sources
    ]


@router.get("/sources/{source_id}", response_model=SourceInfo)
async def get_source(source_id: str) -> SourceInfo:
    """Get a specific source by ID."""
    registry = get_registry()
    source = registry.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")

    return SourceInfo(
        id=source.id,
        name=source.name,
        description=source.description,
        url=source.url,
        source_level=source.source_level.value,
        geographic=source.geographic,
        record_types=source.record_types,
        temporal_start=source.temporal.start,
        temporal_end=source.temporal.end,
    )


@router.post("/route", response_model=RouteResponse)
async def route_search(request: RouteRequest) -> RouteResponse:
    """Get search recommendations for a person or context."""
    smart_router = get_router()

    # Build locations list
    locations = request.locations.copy()
    if request.person:
        if request.person.birth_place:
            locations.append(request.person.birth_place)
        if request.person.death_place:
            locations.append(request.person.death_place)

    # Get year
    year = request.year
    if not year and request.person and request.person.birth_year:
        year = request.person.birth_year

    # Get ethnicities
    ethnicities = request.ethnicities.copy()
    if request.person and request.person.ethnicities:
        ethnicities.extend(request.person.ethnicities)

    # Get surname
    surname = request.surname
    if not surname and request.person:
        surname = request.person.surname

    # Route
    recommendations = smart_router.route(
        surname=surname,
        locations=locations if locations else None,
        year=year,
        ethnicities=ethnicities if ethnicities else None,
    )

    # Convert to response
    response_recs = [
        RecommendationResponse(
            source_id=r.source_id,
            source_name=r.source_name,
            reason=r.reason,
            priority=r.priority,
            source_level=r.source_level.value,
            url=r.url,
            provider=r.provider,
            record_types=r.record_types,
            search_params=r.search_params,
            ai_generated=r.ai_generated,
        )
        for r in recommendations
    ]

    ai_count = sum(1 for r in recommendations if r.ai_generated)

    return RouteResponse(
        recommendations=response_recs,
        total=len(response_recs),
        rule_based=len(response_recs) - ai_count,
        ai_generated=ai_count,
    )


@router.get("/route/quick", response_model=RouteResponse)
async def quick_route(
    surname: str = Query(..., description="Surname to search"),
    location: str | None = Query(None, description="Location (birth place, country, etc.)"),
    year: int | None = Query(None, description="Year (birth year)"),
    ethnicity: str | None = Query(None, description="Ethnicity/cultural marker"),
) -> RouteResponse:
    """Quick route with query parameters instead of POST body."""
    request = RouteRequest(
        surname=surname,
        locations=[location] if location else [],
        year=year,
        ethnicities=[ethnicity] if ethnicity else [],
    )
    return await route_search(request)
