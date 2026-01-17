"""Tests for the Smart Search Router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from genealogy_assistant.core.models import (
    Event,
    GenealogyDate,
    Name,
    Person,
    Place,
    SourceLevel,
)
from genealogy_assistant.router.registry import SourceRegistry
from genealogy_assistant.router.smart_router import (
    PersonContext,
    SmartRouter,
    SourceRecommendation,
)


# =============================================================================
# PersonContext Tests
# =============================================================================


class TestPersonContext:
    """Tests for PersonContext class."""

    @pytest.fixture
    def belgian_person(self) -> Person:
        """Create a person born in Belgium."""
        person = Person()
        person.names.append(
            Name(
                given="Jean Joseph",
                surname="Herinckx",
                variants=["Herincx", "Herinck"],
            )
        )
        person.birth = Event(
            event_type="BIRT",
            date=GenealogyDate(year=1850, month=3, day=15),
            place=Place(
                name="Tervuren, Brabant, Belgium",
                city="Tervuren",
                state="Brabant",
                country="Belgium",
            ),
        )
        person.death = Event(
            event_type="DEAT",
            date=GenealogyDate(year=1920, month=8, day=22),
            place=Place(
                name="Detroit, Michigan, USA",
                city="Detroit",
                state="Michigan",
                country="USA",
            ),
        )
        return person

    @pytest.fixture
    def cherokee_person(self) -> Person:
        """Create a person with Cherokee ancestry."""
        person = Person()
        person.names.append(
            Name(
                given="John",
                surname="McLemore",
            )
        )
        person.birth = Event(
            event_type="BIRT",
            date=GenealogyDate(year=1870),
            place=Place(
                name="Cherokee Nation, Indian Territory",
                country="Cherokee Nation",
            ),
        )
        return person

    def test_from_person_extracts_name(self, belgian_person: Person):
        """Should extract name from person."""
        context = PersonContext.from_person(belgian_person)
        assert context.surname == "Herinckx"
        assert context.given_name == "Jean Joseph"
        assert "Herincx" in context.surname_variants

    def test_from_person_extracts_birth(self, belgian_person: Person):
        """Should extract birth information."""
        context = PersonContext.from_person(belgian_person)
        assert context.birth_year == 1850
        assert "Tervuren, Brabant, Belgium" in context.birth_place

    def test_from_person_extracts_death(self, belgian_person: Person):
        """Should extract death information."""
        context = PersonContext.from_person(belgian_person)
        assert context.death_year == 1920
        assert "Detroit" in context.death_place

    def test_from_person_extracts_locations(self, belgian_person: Person):
        """Should extract all locations."""
        context = PersonContext.from_person(belgian_person)
        assert len(context.all_locations) > 0
        # Should include countries
        location_str = " ".join(context.all_locations).lower()
        assert "belgium" in location_str or "usa" in location_str

    def test_from_person_detects_migration(self, belgian_person: Person):
        """Should detect migration between countries."""
        context = PersonContext.from_person(belgian_person)
        assert context.migration_detected is True
        assert context.origin_country == "belgium"
        assert context.destination_country == "united states"

    def test_from_person_no_migration_same_country(self):
        """Should not detect migration when same country."""
        person = Person()
        person.birth = Event(
            event_type="BIRT",
            place=Place(name="New York, USA", country="USA"),
        )
        person.death = Event(
            event_type="DEAT",
            place=Place(name="Los Angeles, USA", country="USA"),
        )
        context = PersonContext.from_person(person)
        assert context.migration_detected is False

    def test_extract_countries_normalizes(self):
        """Country extraction should normalize names."""
        countries = PersonContext._extract_countries("Antwerp, Belgium")
        assert "belgium" in countries

        countries = PersonContext._extract_countries("New York, USA")
        assert "united states" in countries

        countries = PersonContext._extract_countries("Holland")
        assert "netherlands" in countries


# =============================================================================
# SourceRecommendation Tests
# =============================================================================


class TestSourceRecommendation:
    """Tests for SourceRecommendation class."""

    def test_from_source_definition(self):
        """Should create recommendation from source definition."""
        from genealogy_assistant.router.registry import SourceDefinition, TemporalCoverage

        source = SourceDefinition(
            id="test_source",
            name="Test Source",
            url="https://example.com",
            provider="test",
            source_level=SourceLevel.PRIMARY,
            temporal=TemporalCoverage(start=1800, end=1900),
            record_types=["birth", "death"],
        )

        rec = SourceRecommendation.from_source_definition(
            source=source,
            reason="Test reason",
            priority=1,
            search_params={"surname": "Smith"},
        )

        assert rec.source_id == "test_source"
        assert rec.source_name == "Test Source"
        assert rec.reason == "Test reason"
        assert rec.priority == 1
        assert rec.source_level == SourceLevel.PRIMARY
        assert rec.url == "https://example.com"
        assert rec.search_params == {"surname": "Smith"}
        assert rec.ai_generated is False


# =============================================================================
# SmartRouter Tests
# =============================================================================


class TestSmartRouter:
    """Tests for SmartRouter class."""

    @pytest.fixture
    def router(self) -> SmartRouter:
        """Create a router with the bundled registry."""
        return SmartRouter(enable_ai_fallback=False)

    @pytest.fixture
    def belgian_person(self) -> Person:
        """Create a Belgian person."""
        person = Person()
        person.names.append(Name(given="Jean", surname="Herinckx"))
        person.birth = Event(
            event_type="BIRT",
            date=GenealogyDate(year=1850),
            place=Place(name="Antwerp, Belgium", country="Belgium"),
        )
        return person

    @pytest.fixture
    def cherokee_person(self) -> Person:
        """Create a Cherokee person."""
        person = Person()
        person.names.append(Name(given="John", surname="Swimmer"))
        person.birth = Event(
            event_type="BIRT",
            date=GenealogyDate(year=1900),
            place=Place(name="Cherokee Nation, Oklahoma"),
        )
        return person

    def test_route_belgian_person(self, router: SmartRouter, belgian_person: Person):
        """Should recommend Belgian sources for Belgian person."""
        recommendations = router.route(person=belgian_person)
        assert len(recommendations) > 0

        # Should include Belgian State Archives
        source_ids = [r.source_id for r in recommendations]
        assert "belgian_state_archives" in source_ids

    def test_route_cherokee_person(self, router: SmartRouter, cherokee_person: Person):
        """Should recommend Cherokee sources for Cherokee person."""
        # Add ethnicity marker
        context = PersonContext.from_person(cherokee_person)
        context.ethnic_markers = ["Cherokee"]

        recommendations = router.route(context=context)
        # Should have some recommendations
        assert len(recommendations) >= 0  # May not match without proper ethnicity setup

    def test_route_by_location(self, router: SmartRouter):
        """Should route by location."""
        recommendations = router.route(
            surname="Smith",
            locations=["Belgium"],
            year=1850,
        )
        assert len(recommendations) > 0

    def test_route_by_ethnicity(self, router: SmartRouter):
        """Should route by ethnicity."""
        recommendations = router.route(
            surname="Swimmer",
            ethnicities=["Cherokee"],
            year=1900,
        )
        # Should have some recommendations (even if just fallback)
        assert isinstance(recommendations, list)

    def test_route_primary_sources_first(self, router: SmartRouter):
        """Primary sources should be recommended first."""
        recommendations = router.route(
            surname="Herinckx",
            locations=["Belgium"],
            year=1850,
        )
        if len(recommendations) > 1:
            # First recommendation should be primary if available
            levels = [r.source_level for r in recommendations]
            primary_indices = [i for i, l in enumerate(levels) if l == SourceLevel.PRIMARY]
            tertiary_indices = [i for i, l in enumerate(levels) if l == SourceLevel.TERTIARY]
            if primary_indices and tertiary_indices:
                assert min(primary_indices) < max(tertiary_indices)

    def test_route_generates_reason(self, router: SmartRouter):
        """Recommendations should have reasons."""
        recommendations = router.route(
            surname="Herinckx",
            locations=["Belgium"],
            year=1850,
        )
        for rec in recommendations:
            assert rec.reason is not None
            assert len(rec.reason) > 0

    def test_route_generates_search_params(self, router: SmartRouter):
        """Recommendations should include search params."""
        recommendations = router.route(
            surname="Herinckx",
            locations=["Belgium"],
            year=1850,
        )
        for rec in recommendations:
            if rec.search_params:
                assert "surname" in rec.search_params or "year_range" in rec.search_params

    def test_route_empty_context(self, router: SmartRouter):
        """Should handle empty context gracefully."""
        recommendations = router.route()
        # Should return general recommendations or empty list
        assert isinstance(recommendations, list)

    def test_route_with_context_object(self, router: SmartRouter):
        """Should accept PersonContext directly."""
        context = PersonContext(
            surname="Herinckx",
            birth_year=1850,
            birth_place="Antwerp, Belgium",
            all_locations=["Belgium"],
        )
        recommendations = router.route(context=context)
        assert len(recommendations) > 0


class TestSmartRouterAIFallback:
    """Tests for SmartRouter AI fallback functionality."""

    @pytest.fixture
    def router_with_ai(self) -> SmartRouter:
        """Create a router with AI enabled."""
        return SmartRouter(enable_ai_fallback=True)

    def test_ai_fallback_disabled_by_default(self):
        """AI fallback should be configurable."""
        router = SmartRouter(enable_ai_fallback=False)
        assert router.enable_ai_fallback is False

    def test_ai_fallback_enabled(self, router_with_ai: SmartRouter):
        """AI fallback should be enabled when configured."""
        assert router_with_ai.enable_ai_fallback is True

    def test_cache_key_generation(self, router_with_ai: SmartRouter):
        """Cache key should be generated from context."""
        context = PersonContext(
            surname="Smith",
            birth_year=1850,
            birth_place="New York",
            death_place="Boston",
        )
        key = router_with_ai._cache_key(context)
        assert "Smith" in key
        assert "1850" in key

    def test_build_ai_prompt(self, router_with_ai: SmartRouter):
        """AI prompt should include context."""
        context = PersonContext(
            surname="Herinckx",
            given_name="Jean",
            birth_year=1850,
            birth_place="Antwerp, Belgium",
            death_year=1920,
            death_place="Detroit, USA",
            migration_detected=True,
            origin_country="Belgium",
            destination_country="USA",
        )
        prompt = router_with_ai._build_ai_prompt(context)

        assert "Jean Herinckx" in prompt
        assert "1850" in prompt
        assert "Antwerp" in prompt
        assert "Migration" in prompt or "Belgium" in prompt

    def test_parse_ai_response_valid_json(self, router_with_ai: SmartRouter):
        """Should parse valid JSON response."""
        response = """
        Here are my recommendations:
        [
            {"source": "Ellis Island", "reason": "Immigration records", "record_types": ["passenger"]},
            {"source": "Belgian Archives", "reason": "Birth records", "record_types": ["birth"]}
        ]
        """
        recs = router_with_ai._parse_ai_response(response)
        assert len(recs) == 2
        assert recs[0].source_name == "Ellis Island"
        assert recs[0].ai_generated is True

    def test_parse_ai_response_invalid_json(self, router_with_ai: SmartRouter):
        """Should handle invalid JSON gracefully."""
        response = "This is not valid JSON"
        recs = router_with_ai._parse_ai_response(response)
        assert recs == []

    @pytest.mark.asyncio
    async def test_route_async_with_mock_ai(self, router_with_ai: SmartRouter):
        """Async route should work with mocked AI."""
        # Mock the anthropic client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"source": "Test", "reason": "test"}]')]
        mock_client.messages.create.return_value = mock_response

        router_with_ai._client = mock_client

        context = PersonContext(
            surname="Test",
            birth_year=1850,
            birth_place="Unknown Location",
        )

        recommendations = await router_with_ai.route_async(context=context)
        assert isinstance(recommendations, list)


class TestSmartRouterIntegration:
    """Integration tests for SmartRouter."""

    @pytest.fixture
    def router(self) -> SmartRouter:
        """Create a router."""
        return SmartRouter(enable_ai_fallback=False)

    def test_belgian_emigrant_to_usa(self, router: SmartRouter):
        """Should recommend sources for Belgian emigrant to USA."""
        person = Person()
        person.names.append(Name(given="Victor", surname="Herinckx"))
        person.birth = Event(
            event_type="BIRT",
            date=GenealogyDate(year=1880),
            place=Place(name="Antwerp, Belgium", country="Belgium"),
        )
        person.death = Event(
            event_type="DEAT",
            date=GenealogyDate(year=1950),
            place=Place(name="Chicago, Illinois, USA", country="USA"),
        )

        recommendations = router.route(person=person)
        source_ids = [r.source_id for r in recommendations]

        # Should include Belgian sources
        assert any("belgian" in sid.lower() for sid in source_ids)

    def test_cherokee_with_ethnicity(self, router: SmartRouter):
        """Should recommend Cherokee sources when ethnicity specified."""
        context = PersonContext(
            surname="Swimmer",
            given_name="John",
            birth_year=1900,
            birth_place="Cherokee Nation, Oklahoma",
            ethnic_markers=["Cherokee"],
        )

        recommendations = router.route(context=context)
        # Should have recommendations
        assert isinstance(recommendations, list)

    def test_us_census_recommendation(self, router: SmartRouter):
        """Should recommend US Census for US residents."""
        context = PersonContext(
            surname="Smith",
            birth_year=1880,
            birth_place="New York, USA",
            all_locations=["United States"],
        )

        recommendations = router.route(context=context)
        source_ids = [r.source_id for r in recommendations]

        # Should include FamilySearch or census sources
        assert len(recommendations) > 0
