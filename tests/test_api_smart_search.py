"""Tests for the Smart Search API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genealogy_assistant.adapters.gramps_web.api import (
    PersonContext,
    RecommendationResponse,
    RouteRequest,
    RouteResponse,
    SourceInfo,
    get_registry,
    get_router,
    router as smart_search_router,
)


# =============================================================================
# Test App Setup
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with the smart search router."""
    app = FastAPI()
    app.include_router(smart_search_router, prefix="/api")
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestPydanticModels:
    """Tests for Pydantic request/response models."""

    def test_person_context_defaults(self):
        """PersonContext should have sensible defaults."""
        context = PersonContext()
        assert context.surname is None
        assert context.given_name is None
        assert context.ethnicities == []

    def test_person_context_with_values(self):
        """PersonContext should accept values."""
        context = PersonContext(
            surname="Herinckx",
            given_name="Jean",
            birth_year=1850,
            birth_place="Antwerp, Belgium",
            ethnicities=["Belgian"],
        )
        assert context.surname == "Herinckx"
        assert context.birth_year == 1850
        assert "Belgian" in context.ethnicities

    def test_route_request_defaults(self):
        """RouteRequest should have sensible defaults."""
        request = RouteRequest()
        assert request.person is None
        assert request.locations == []
        assert request.ethnicities == []

    def test_route_request_with_person(self):
        """RouteRequest should accept person context."""
        person = PersonContext(surname="Smith", birth_year=1850)
        request = RouteRequest(person=person, year=1850)
        assert request.person.surname == "Smith"
        assert request.year == 1850

    def test_source_info_model(self):
        """SourceInfo should serialize correctly."""
        info = SourceInfo(
            id="test",
            name="Test Source",
            source_level="primary",
            geographic=["USA"],
            record_types=["census"],
        )
        assert info.id == "test"
        assert info.source_level == "primary"

    def test_recommendation_response_model(self):
        """RecommendationResponse should serialize correctly."""
        rec = RecommendationResponse(
            source_id="test",
            source_name="Test Source",
            reason="Test reason",
            priority=1,
            source_level="primary",
            url="https://example.com",
            ai_generated=False,
        )
        assert rec.source_id == "test"
        assert rec.ai_generated is False

    def test_route_response_model(self):
        """RouteResponse should include counts."""
        response = RouteResponse(
            recommendations=[
                RecommendationResponse(
                    source_id="test",
                    source_name="Test",
                    reason="Test",
                    priority=1,
                    source_level="primary",
                    ai_generated=False,
                )
            ],
            total=1,
            rule_based=1,
            ai_generated=0,
        )
        assert response.total == 1
        assert response.rule_based == 1
        assert response.ai_generated == 0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingletons:
    """Tests for singleton instances."""

    def test_get_registry_returns_same_instance(self):
        """get_registry should return same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_get_router_returns_same_instance(self):
        """get_router should return same instance."""
        router1 = get_router()
        router2 = get_router()
        assert router1 is router2


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestListSourcesEndpoint:
    """Tests for GET /smart-search/sources endpoint."""

    def test_list_sources_returns_list(self, client: TestClient):
        """Should return a list of sources."""
        response = client.get("/api/smart-search/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_sources_has_required_fields(self, client: TestClient):
        """Each source should have required fields."""
        response = client.get("/api/smart-search/sources")
        data = response.json()
        for source in data:
            assert "id" in source
            assert "name" in source
            assert "source_level" in source

    def test_list_sources_filter_by_location(self, client: TestClient):
        """Should filter sources by location."""
        response = client.get("/api/smart-search/sources?location=Belgium")
        assert response.status_code == 200
        data = response.json()
        # Should have Belgian sources
        assert any("Belgian" in s["name"] or "Belgium" in str(s["geographic"]) for s in data)

    def test_list_sources_filter_by_year(self, client: TestClient):
        """Should filter sources by year."""
        response = client.get("/api/smart-search/sources?year=1850")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_sources_filter_by_source_level(self, client: TestClient):
        """Should filter sources by source level."""
        response = client.get("/api/smart-search/sources?source_level=primary")
        assert response.status_code == 200
        data = response.json()
        assert all(s["source_level"] == "primary" for s in data)

    def test_list_sources_invalid_source_level(self, client: TestClient):
        """Should return 400 for invalid source level."""
        response = client.get("/api/smart-search/sources?source_level=invalid")
        assert response.status_code == 400


class TestGetSourceEndpoint:
    """Tests for GET /smart-search/sources/{source_id} endpoint."""

    def test_get_source_by_id(self, client: TestClient):
        """Should return source by ID."""
        response = client.get("/api/smart-search/sources/dawes_rolls")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "dawes_rolls"
        assert "Dawes" in data["name"]

    def test_get_source_not_found(self, client: TestClient):
        """Should return 404 for unknown source."""
        response = client.get("/api/smart-search/sources/nonexistent")
        assert response.status_code == 404

    def test_get_source_has_all_fields(self, client: TestClient):
        """Source response should have all fields."""
        response = client.get("/api/smart-search/sources/belgian_state_archives")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "source_level" in data
        assert "geographic" in data
        assert "record_types" in data


class TestRouteEndpoint:
    """Tests for POST /smart-search/route endpoint."""

    def test_route_with_surname_and_location(self, client: TestClient):
        """Should return recommendations for surname and location."""
        response = client.post(
            "/api/smart-search/route",
            json={
                "surname": "Herinckx",
                "locations": ["Belgium"],
                "year": 1850,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert "total" in data
        assert len(data["recommendations"]) > 0

    def test_route_with_person_context(self, client: TestClient):
        """Should accept person context."""
        response = client.post(
            "/api/smart-search/route",
            json={
                "person": {
                    "surname": "Herinckx",
                    "given_name": "Jean",
                    "birth_year": 1850,
                    "birth_place": "Antwerp, Belgium",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) > 0

    def test_route_with_ethnicities(self, client: TestClient):
        """Should accept ethnicities."""
        response = client.post(
            "/api/smart-search/route",
            json={
                "surname": "Swimmer",
                "ethnicities": ["Cherokee"],
                "year": 1900,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data

    def test_route_recommendations_have_required_fields(self, client: TestClient):
        """Recommendations should have required fields."""
        response = client.post(
            "/api/smart-search/route",
            json={
                "surname": "Smith",
                "locations": ["United States"],
                "year": 1900,
            },
        )
        data = response.json()
        for rec in data["recommendations"]:
            assert "source_id" in rec
            assert "source_name" in rec
            assert "reason" in rec
            assert "priority" in rec
            assert "source_level" in rec

    def test_route_returns_counts(self, client: TestClient):
        """Response should include counts."""
        response = client.post(
            "/api/smart-search/route",
            json={"surname": "Smith", "locations": ["Belgium"], "year": 1850},
        )
        data = response.json()
        assert "total" in data
        assert "rule_based" in data
        assert "ai_generated" in data
        assert data["total"] == data["rule_based"] + data["ai_generated"]

    def test_route_empty_request(self, client: TestClient):
        """Should handle empty request gracefully."""
        response = client.post("/api/smart-search/route", json={})
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data


class TestQuickRouteEndpoint:
    """Tests for GET /smart-search/route/quick endpoint."""

    def test_quick_route_basic(self, client: TestClient):
        """Should return recommendations with query params."""
        response = client.get(
            "/api/smart-search/route/quick?surname=Herinckx&location=Belgium&year=1850"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) > 0

    def test_quick_route_surname_required(self, client: TestClient):
        """Surname should be required."""
        response = client.get("/api/smart-search/route/quick")
        assert response.status_code == 422  # Validation error

    def test_quick_route_with_ethnicity(self, client: TestClient):
        """Should accept ethnicity parameter."""
        response = client.get(
            "/api/smart-search/route/quick?surname=Swimmer&ethnicity=Cherokee&year=1900"
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data

    def test_quick_route_optional_params(self, client: TestClient):
        """Optional params should be optional."""
        response = client.get("/api/smart-search/route/quick?surname=Smith")
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data


# =============================================================================
# Integration Tests
# =============================================================================


class TestAPIIntegration:
    """Integration tests for the Smart Search API."""

    def test_belgian_research_workflow(self, client: TestClient):
        """Test workflow for Belgian genealogy research."""
        # 1. Check available Belgian sources
        response = client.get("/api/smart-search/sources?location=Belgium")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) > 0

        # 2. Get recommendations for a Belgian person
        response = client.post(
            "/api/smart-search/route",
            json={
                "person": {
                    "surname": "Herinckx",
                    "birth_year": 1850,
                    "birth_place": "Antwerp, Belgium",
                },
            },
        )
        assert response.status_code == 200
        recs = response.json()["recommendations"]
        assert len(recs) > 0

        # 3. Verify Belgian State Archives is recommended
        source_ids = [r["source_id"] for r in recs]
        assert "belgian_state_archives" in source_ids

    def test_cherokee_research_workflow(self, client: TestClient):
        """Test workflow for Cherokee genealogy research."""
        # 1. Get recommendations with Cherokee ethnicity
        response = client.post(
            "/api/smart-search/route",
            json={
                "surname": "Swimmer",
                "ethnicities": ["Cherokee"],
                "year": 1900,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data

    def test_primary_sources_prioritized(self, client: TestClient):
        """Primary sources should appear before tertiary."""
        response = client.post(
            "/api/smart-search/route",
            json={
                "surname": "Smith",
                "locations": ["Belgium"],
                "year": 1850,
            },
        )
        data = response.json()
        recs = data["recommendations"]

        if len(recs) > 1:
            levels = [r["source_level"] for r in recs]
            # Find first primary and last tertiary
            primary_indices = [i for i, l in enumerate(levels) if l == "primary"]
            tertiary_indices = [i for i, l in enumerate(levels) if l == "tertiary"]

            if primary_indices and tertiary_indices:
                # Primary should come before tertiary
                assert min(primary_indices) < max(tertiary_indices)
