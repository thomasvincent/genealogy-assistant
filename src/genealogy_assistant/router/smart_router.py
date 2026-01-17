"""Smart Search Router with AI fallback.

Routes genealogical searches to appropriate databases based on context.
Uses rule-based matching for common cases, falls back to AI for complex cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from genealogy_assistant.core.models import Person, SourceLevel
from genealogy_assistant.router.registry import SourceDefinition, SourceRegistry


@dataclass
class SourceRecommendation:
    """Recommendation to search a specific source."""

    source_id: str
    source_name: str
    reason: str
    priority: int
    source_level: SourceLevel
    url: str | None = None
    provider: str | None = None
    record_types: list[str] = field(default_factory=list)
    search_params: dict[str, Any] = field(default_factory=dict)
    ai_generated: bool = False

    @classmethod
    def from_source_definition(
        cls,
        source: SourceDefinition,
        reason: str,
        priority: int,
        search_params: dict[str, Any] | None = None,
    ) -> SourceRecommendation:
        """Create recommendation from source definition."""
        return cls(
            source_id=source.id,
            source_name=source.name,
            reason=reason,
            priority=priority,
            source_level=source.source_level,
            url=source.url,
            provider=source.provider,
            record_types=source.record_types,
            search_params=search_params or {},
            ai_generated=False,
        )


@dataclass
class PersonContext:
    """Extracted context from a Person for routing decisions."""

    surname: str | None = None
    given_name: str | None = None
    surname_variants: list[str] = field(default_factory=list)

    # Locations
    birth_place: str | None = None
    death_place: str | None = None
    residence_places: list[str] = field(default_factory=list)
    all_locations: list[str] = field(default_factory=list)

    # Time
    birth_year: int | None = None
    death_year: int | None = None

    # Ethnicity/cultural markers
    ethnic_markers: list[str] = field(default_factory=list)

    # Migration
    migration_detected: bool = False
    origin_country: str | None = None
    destination_country: str | None = None

    @classmethod
    def from_person(cls, person: Person) -> PersonContext:
        """Extract context from a Person model."""
        context = cls()

        # Extract names
        if person.primary_name:
            context.surname = person.primary_name.surname
            context.given_name = person.primary_name.given
            context.surname_variants = person.primary_name.variants.copy()

        # Extract locations
        locations = []
        if person.birth and person.birth.place:
            context.birth_place = person.birth.place.name
            locations.append(person.birth.place.name)
            if person.birth.place.country:
                locations.append(person.birth.place.country)
            if person.birth.place.state:
                locations.append(person.birth.place.state)

        if person.death and person.death.place:
            context.death_place = person.death.place.name
            locations.append(person.death.place.name)
            if person.death.place.country:
                locations.append(person.death.place.country)

        # Extract residence from events
        for event in person.events:
            if event.event_type == "RESI" and event.place:
                context.residence_places.append(event.place.name)
                locations.append(event.place.name)

        context.all_locations = list(set(locations))

        # Extract dates
        context.birth_year = person.birth_year()
        context.death_year = person.death_year()

        # Detect migration
        if context.birth_place and context.death_place:
            birth_countries = cls._extract_countries(context.birth_place)
            death_countries = cls._extract_countries(context.death_place)
            if birth_countries and death_countries and birth_countries != death_countries:
                context.migration_detected = True
                context.origin_country = list(birth_countries)[0]
                context.destination_country = list(death_countries)[0]

        return context

    @staticmethod
    def _extract_countries(place_str: str) -> set[str]:
        """Extract country names from place string."""
        known_countries = {
            "united states", "usa", "us", "america",
            "belgium", "belgie", "belgique",
            "netherlands", "holland", "nederland",
            "germany", "deutschland",
            "france",
            "ireland",
            "england", "uk", "united kingdom",
            "cherokee nation", "indian territory", "oklahoma",
        }

        place_lower = place_str.lower()
        found = set()
        for country in known_countries:
            if country in place_lower:
                # Normalize country names
                if country in ("usa", "us", "america"):
                    found.add("united states")
                elif country in ("belgie", "belgique"):
                    found.add("belgium")
                elif country in ("holland", "nederland"):
                    found.add("netherlands")
                elif country in ("deutschland",):
                    found.add("germany")
                elif country in ("uk", "england"):
                    found.add("united kingdom")
                elif country in ("cherokee nation", "indian territory"):
                    found.add("oklahoma")
                else:
                    found.add(country)
        return found


class SmartRouter:
    """
    Smart Search Router with rule-based matching and AI fallback.

    Routes genealogical searches to appropriate databases based on:
    - Geographic location
    - Time period
    - Ethnic/cultural markers
    - Migration patterns
    """

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        anthropic_client: AsyncAnthropic | None = None,
        enable_ai_fallback: bool = True,
        ai_model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize the router."""
        self.registry = registry or SourceRegistry()
        self._client = anthropic_client
        self.enable_ai_fallback = enable_ai_fallback
        self.ai_model = ai_model

        # Cache for AI recommendations
        self._ai_cache: dict[str, list[SourceRecommendation]] = {}

    def route(
        self,
        person: Person | None = None,
        context: PersonContext | None = None,
        surname: str | None = None,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
    ) -> list[SourceRecommendation]:
        """
        Get source recommendations for a person or context.

        Args:
            person: Person model to route for
            context: Pre-extracted PersonContext
            surname: Surname to search (if not using person)
            locations: Locations to consider
            year: Year to consider
            ethnicities: Ethnic markers to consider

        Returns:
            Prioritized list of source recommendations
        """
        # Extract context from person if provided
        if person and not context:
            context = PersonContext.from_person(person)

        # Build search parameters
        if context:
            locations = locations or context.all_locations
            year = year or context.birth_year
            ethnicities = ethnicities or context.ethnic_markers
            surname = surname or context.surname

        # Get rule-based recommendations
        recommendations = self._route_by_rules(
            locations=locations,
            year=year,
            ethnicities=ethnicities,
            surname=surname,
        )

        # If no recommendations and AI fallback enabled, try AI
        if not recommendations and self.enable_ai_fallback and context:
            # AI fallback would be called here (async)
            # For sync usage, recommendations remain empty
            pass

        return recommendations

    async def route_async(
        self,
        person: Person | None = None,
        context: PersonContext | None = None,
        surname: str | None = None,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
    ) -> list[SourceRecommendation]:
        """
        Async version of route with AI fallback support.
        """
        # Extract context from person if provided
        if person and not context:
            context = PersonContext.from_person(person)

        # Build search parameters
        if context:
            locations = locations or context.all_locations
            year = year or context.birth_year
            ethnicities = ethnicities or context.ethnic_markers
            surname = surname or context.surname

        # Get rule-based recommendations
        recommendations = self._route_by_rules(
            locations=locations,
            year=year,
            ethnicities=ethnicities,
            surname=surname,
        )

        # If few recommendations and AI fallback enabled, supplement with AI
        if len(recommendations) < 3 and self.enable_ai_fallback and context:
            ai_recs = await self._get_ai_recommendations(context)
            # Add AI recommendations that aren't already included
            existing_ids = {r.source_id for r in recommendations}
            for rec in ai_recs:
                if rec.source_id not in existing_ids:
                    recommendations.append(rec)

        return recommendations

    def _route_by_rules(
        self,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
        surname: str | None = None,
    ) -> list[SourceRecommendation]:
        """Get recommendations using rule-based matching."""
        recommendations: list[SourceRecommendation] = []

        # Get sources from matching rules
        rule_sources = self.registry.get_sources_by_rules(
            locations=locations,
            year=year,
            ethnicities=ethnicities,
        )

        for i, source in enumerate(rule_sources):
            reason = self._generate_reason(source, locations, year, ethnicities)
            search_params = self._build_search_params(source, surname, year)

            recommendations.append(
                SourceRecommendation.from_source_definition(
                    source=source,
                    reason=reason,
                    priority=i + 1,
                    search_params=search_params,
                )
            )

        # If no rule matches, fall back to general source search
        if not recommendations:
            general_sources = self.registry.find_sources(
                locations=locations,
                year=year,
                ethnicities=ethnicities,
            )

            for i, source in enumerate(general_sources[:10]):  # Limit to 10
                reason = self._generate_reason(source, locations, year, ethnicities)
                search_params = self._build_search_params(source, surname, year)

                recommendations.append(
                    SourceRecommendation.from_source_definition(
                        source=source,
                        reason=reason,
                        priority=i + 1,
                        search_params=search_params,
                    )
                )

        return recommendations

    def _generate_reason(
        self,
        source: SourceDefinition,
        locations: list[str] | None,
        year: int | None,
        ethnicities: list[str] | None,
    ) -> str:
        """Generate human-readable reason for recommendation."""
        reasons = []

        if locations:
            matching_geo = [g for g in source.geographic if any(g.lower() in loc.lower() or loc.lower() in g.lower() for loc in locations)]
            if matching_geo:
                reasons.append(f"covers {', '.join(matching_geo[:2])}")

        if year and source.temporal.start and source.temporal.end:
            reasons.append(f"records from {source.temporal.start}-{source.temporal.end}")

        if ethnicities and source.ethnic_markers:
            matching = [m for m in source.ethnic_markers if any(m.lower() in e.lower() for e in ethnicities)]
            if matching:
                reasons.append(f"includes {', '.join(matching[:2])} records")

        if source.source_level == SourceLevel.PRIMARY:
            reasons.append("primary source")

        if not reasons:
            reasons.append(f"general {source.record_types[0] if source.record_types else 'genealogy'} database")

        return "; ".join(reasons)

    def _build_search_params(
        self,
        source: SourceDefinition,
        surname: str | None,
        year: int | None,
    ) -> dict[str, Any]:
        """Build search parameters for the source."""
        params: dict[str, Any] = {}

        if surname:
            params["surname"] = surname

        if year:
            # Most databases support a year range
            params["year_range"] = f"{year - 5}-{year + 5}"

        return params

    async def _get_ai_recommendations(
        self,
        context: PersonContext,
    ) -> list[SourceRecommendation]:
        """Get AI-generated source recommendations."""
        if not self._client:
            return []

        # Check cache
        cache_key = self._cache_key(context)
        if cache_key in self._ai_cache:
            return self._ai_cache[cache_key]

        # Build prompt
        prompt = self._build_ai_prompt(context)

        try:
            response = await self._client.messages.create(
                model=self.ai_model,
                max_tokens=1024,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            recommendations = self._parse_ai_response(response.content[0].text)

            # Cache results
            self._ai_cache[cache_key] = recommendations

            return recommendations

        except Exception:
            # Fail gracefully - AI is optional
            return []

    def _cache_key(self, context: PersonContext) -> str:
        """Generate cache key for context."""
        parts = [
            context.surname or "",
            str(context.birth_year or ""),
            context.birth_place or "",
            context.death_place or "",
        ]
        return ":".join(parts)

    def _build_ai_prompt(self, context: PersonContext) -> str:
        """Build prompt for AI source recommendations."""
        lines = ["Suggest genealogical databases to search for this person:"]
        lines.append("")

        if context.surname:
            lines.append(f"Name: {context.given_name or ''} {context.surname}")
        if context.birth_year and context.birth_place:
            lines.append(f"Birth: {context.birth_year}, {context.birth_place}")
        if context.death_year and context.death_place:
            lines.append(f"Death: {context.death_year}, {context.death_place}")
        if context.migration_detected:
            lines.append(f"Migration: {context.origin_country} → {context.destination_country}")
        if context.ethnic_markers:
            lines.append(f"Ethnicity: {', '.join(context.ethnic_markers)}")

        lines.append("")
        lines.append("Return a JSON array of recommendations:")
        lines.append('[{"source": "name", "reason": "why", "record_types": ["type"]}]')
        lines.append("")
        lines.append("Consider: immigration records, naturalization, census, vital records, church records.")
        lines.append("Prioritize primary sources over indexes.")

        return "\n".join(lines)

    def _parse_ai_response(self, response: str) -> list[SourceRecommendation]:
        """Parse AI response into recommendations."""
        import json
        import re

        recommendations = []

        # Try to extract JSON from response
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return recommendations

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return recommendations

        for i, item in enumerate(data):
            if isinstance(item, dict):
                recommendations.append(
                    SourceRecommendation(
                        source_id=item.get("source", "unknown").lower().replace(" ", "_"),
                        source_name=item.get("source", "Unknown"),
                        reason=item.get("reason", "AI recommended"),
                        priority=i + 100,  # Lower priority than rule-based
                        source_level=SourceLevel.TERTIARY,
                        record_types=item.get("record_types", []),
                        ai_generated=True,
                    )
                )

        return recommendations
