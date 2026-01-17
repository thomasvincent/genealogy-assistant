"""Source Registry for genealogical databases.

Loads source definitions from YAML and provides query methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from genealogy_assistant.core.models import SourceLevel


@dataclass
class TemporalCoverage:
    """Time period coverage for a source."""

    start: int | None = None
    end: int | None = None

    def contains_year(self, year: int) -> bool:
        """Check if year falls within coverage."""
        if self.start and year < self.start:
            return False
        if self.end and year > self.end:
            return False
        return True

    def overlaps(self, start: int | None, end: int | None) -> bool:
        """Check if time ranges overlap."""
        if start is None and end is None:
            return True
        if self.start is None and self.end is None:
            return True

        range_start = start or 0
        range_end = end or 9999
        self_start = self.start or 0
        self_end = self.end or 9999

        return range_start <= self_end and range_end >= self_start


@dataclass
class SourceDefinition:
    """Definition of a genealogical source/database."""

    id: str
    name: str
    description: str | None = None
    url: str | None = None
    api_endpoint: str | None = None
    provider: str | None = None
    source_level: SourceLevel = SourceLevel.TERTIARY

    # Coverage
    geographic: list[str] = field(default_factory=list)
    temporal: TemporalCoverage = field(default_factory=TemporalCoverage)
    record_types: list[str] = field(default_factory=list)
    ethnic_markers: list[str] = field(default_factory=list)

    notes: str | None = None

    @classmethod
    def from_dict(cls, id: str, data: dict[str, Any]) -> SourceDefinition:
        """Create from dictionary (YAML data)."""
        coverage = data.get("coverage", {})

        temporal_data = coverage.get("temporal", {})
        temporal = TemporalCoverage(
            start=temporal_data.get("start"),
            end=temporal_data.get("end"),
        )

        # Parse source level
        level_str = data.get("source_level", "tertiary")
        try:
            source_level = SourceLevel(level_str)
        except ValueError:
            source_level = SourceLevel.TERTIARY

        return cls(
            id=id,
            name=data.get("name", id),
            description=data.get("description"),
            url=data.get("url"),
            api_endpoint=data.get("api_endpoint"),
            provider=data.get("provider"),
            source_level=source_level,
            geographic=coverage.get("geographic", []),
            temporal=temporal,
            record_types=data.get("record_types", []),
            ethnic_markers=data.get("ethnic_markers", []),
            notes=data.get("notes"),
        )

    def matches_location(self, locations: list[str]) -> bool:
        """Check if source covers any of the given locations."""
        if not self.geographic:
            return True  # No geographic restriction
        if not locations:
            return True  # No location specified

        locations_lower = [loc.lower() for loc in locations]
        for geo in self.geographic:
            if geo.lower() in locations_lower:
                return True
            # Check partial matches
            for loc in locations_lower:
                if geo.lower() in loc or loc in geo.lower():
                    return True
        return False

    def matches_time(self, year: int | None = None, start: int | None = None, end: int | None = None) -> bool:
        """Check if source covers the given time period."""
        if year:
            return self.temporal.contains_year(year)
        return self.temporal.overlaps(start, end)

    def matches_ethnicity(self, ethnicities: list[str]) -> bool:
        """Check if source is relevant for given ethnic markers."""
        if not self.ethnic_markers:
            return True  # No ethnic restriction
        if not ethnicities:
            return True  # No ethnicity specified

        ethnicities_lower = [e.lower() for e in ethnicities]
        for marker in self.ethnic_markers:
            if marker.lower() in ethnicities_lower:
                return True
        return False


@dataclass
class RoutingRule:
    """Rule for automatic source selection."""

    name: str
    conditions: dict[str, Any]
    sources: list[str]
    priority: int = 10

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingRule:
        """Create from dictionary (YAML data)."""
        return cls(
            name=data.get("name", "unnamed"),
            conditions=data.get("conditions", {}),
            sources=data.get("sources", []),
            priority=data.get("priority", 10),
        )

    def matches(
        self,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
        record_types: list[str] | None = None,
    ) -> bool:
        """Check if rule conditions match the given context."""
        conditions = self.conditions

        # Check geographic conditions
        if "geographic" in conditions:
            if not locations:
                return False
            geo_conditions = [g.lower() for g in conditions["geographic"]]
            locations_lower = [loc.lower() for loc in locations]
            if not any(g in loc or loc in g for g in geo_conditions for loc in locations_lower):
                return False

        # Check temporal conditions
        if "temporal" in conditions:
            if year is None:
                return False
            temporal = conditions["temporal"]
            start = temporal.get("start", 0)
            end = temporal.get("end", 9999)
            if not (start <= year <= end):
                return False

        # Check ethnic markers
        if "ethnic_markers" in conditions:
            if not ethnicities:
                return False
            markers = [m.lower() for m in conditions["ethnic_markers"]]
            ethnicities_lower = [e.lower() for e in ethnicities]
            if not any(m in ethnicities_lower for m in markers):
                return False

        # Check record types
        if "record_types" in conditions:
            if not record_types:
                return False
            req_types = [t.lower() for t in conditions["record_types"]]
            record_types_lower = [t.lower() for t in record_types]
            if not any(t in record_types_lower for t in req_types):
                return False

        return True


class SourceRegistry:
    """Registry of genealogical sources loaded from YAML."""

    def __init__(self, sources_path: Path | str | None = None):
        """Initialize registry from YAML file."""
        if sources_path is None:
            # Default to bundled sources.yaml
            sources_path = Path(__file__).parent.parent / "data" / "sources.yaml"

        self._sources_path = Path(sources_path)
        self._sources: dict[str, SourceDefinition] = {}
        self._rules: list[RoutingRule] = []
        self._load()

    def _load(self) -> None:
        """Load sources from YAML file."""
        if not self._sources_path.exists():
            raise FileNotFoundError(f"Sources file not found: {self._sources_path}")

        with open(self._sources_path) as f:
            data = yaml.safe_load(f)

        # Load sources
        sources_data = data.get("sources", {})
        for source_id, source_data in sources_data.items():
            self._sources[source_id] = SourceDefinition.from_dict(source_id, source_data)

        # Load routing rules
        rules_data = data.get("routing_rules", [])
        for rule_data in rules_data:
            self._rules.append(RoutingRule.from_dict(rule_data))

        # Sort rules by priority (lower = higher priority)
        self._rules.sort(key=lambda r: r.priority)

    def get_source(self, source_id: str) -> SourceDefinition | None:
        """Get source by ID."""
        return self._sources.get(source_id)

    def get_sources(self, source_ids: list[str]) -> list[SourceDefinition]:
        """Get multiple sources by IDs."""
        return [self._sources[sid] for sid in source_ids if sid in self._sources]

    def all_sources(self) -> list[SourceDefinition]:
        """Get all registered sources."""
        return list(self._sources.values())

    def find_sources(
        self,
        locations: list[str] | None = None,
        year: int | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        ethnicities: list[str] | None = None,
        record_types: list[str] | None = None,
        source_level: SourceLevel | None = None,
    ) -> list[SourceDefinition]:
        """Find sources matching the given criteria."""
        results = []

        for source in self._sources.values():
            # Check location
            if locations and not source.matches_location(locations):
                continue

            # Check time
            if year and not source.matches_time(year=year):
                continue
            if (start_year or end_year) and not source.matches_time(start=start_year, end=end_year):
                continue

            # Check ethnicity
            if ethnicities and not source.matches_ethnicity(ethnicities):
                continue

            # Check record types
            if record_types:
                source_types = [t.lower() for t in source.record_types]
                req_types = [t.lower() for t in record_types]
                if not any(t in source_types for t in req_types):
                    continue

            # Check source level
            if source_level and source.source_level != source_level:
                continue

            results.append(source)

        # Sort by source level (primary first)
        level_order = {SourceLevel.PRIMARY: 0, SourceLevel.SECONDARY: 1, SourceLevel.TERTIARY: 2}
        results.sort(key=lambda s: level_order.get(s.source_level, 3))

        return results

    def get_matching_rules(
        self,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
        record_types: list[str] | None = None,
    ) -> list[RoutingRule]:
        """Get routing rules that match the given context."""
        return [
            rule
            for rule in self._rules
            if rule.matches(locations, year, ethnicities, record_types)
        ]

    def get_sources_by_rules(
        self,
        locations: list[str] | None = None,
        year: int | None = None,
        ethnicities: list[str] | None = None,
        record_types: list[str] | None = None,
    ) -> list[SourceDefinition]:
        """Get sources recommended by matching routing rules."""
        matching_rules = self.get_matching_rules(locations, year, ethnicities, record_types)

        # Collect unique source IDs, maintaining priority order
        seen_ids: set[str] = set()
        ordered_ids: list[str] = []

        for rule in matching_rules:
            for source_id in rule.sources:
                if source_id not in seen_ids:
                    seen_ids.add(source_id)
                    ordered_ids.append(source_id)

        return self.get_sources(ordered_ids)

    def __len__(self) -> int:
        """Return number of registered sources."""
        return len(self._sources)

    def __repr__(self) -> str:
        return f"SourceRegistry({len(self._sources)} sources, {len(self._rules)} rules)"
