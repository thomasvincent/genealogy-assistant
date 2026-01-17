"""Tests for the Source Registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_assistant.core.models import SourceLevel
from genealogy_assistant.router.registry import (
    RoutingRule,
    SourceDefinition,
    SourceRegistry,
    TemporalCoverage,
)


# =============================================================================
# TemporalCoverage Tests
# =============================================================================


class TestTemporalCoverage:
    """Tests for TemporalCoverage class."""

    def test_contains_year_in_range(self):
        """Year within range should return True."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.contains_year(1850) is True

    def test_contains_year_at_start(self):
        """Year at start boundary should return True."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.contains_year(1800) is True

    def test_contains_year_at_end(self):
        """Year at end boundary should return True."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.contains_year(1900) is True

    def test_contains_year_before_start(self):
        """Year before start should return False."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.contains_year(1799) is False

    def test_contains_year_after_end(self):
        """Year after end should return False."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.contains_year(1901) is False

    def test_contains_year_no_start(self):
        """No start boundary should match any year before end."""
        coverage = TemporalCoverage(start=None, end=1900)
        assert coverage.contains_year(1500) is True
        assert coverage.contains_year(1901) is False

    def test_contains_year_no_end(self):
        """No end boundary should match any year after start."""
        coverage = TemporalCoverage(start=1800, end=None)
        assert coverage.contains_year(2000) is True
        assert coverage.contains_year(1799) is False

    def test_contains_year_no_bounds(self):
        """No bounds should match any year."""
        coverage = TemporalCoverage(start=None, end=None)
        assert coverage.contains_year(1500) is True
        assert coverage.contains_year(2000) is True

    def test_overlaps_with_range(self):
        """Overlapping ranges should return True."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.overlaps(1850, 1950) is True

    def test_overlaps_contained_range(self):
        """Contained range should return True."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.overlaps(1850, 1875) is True

    def test_overlaps_no_overlap(self):
        """Non-overlapping ranges should return False."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.overlaps(1950, 2000) is False

    def test_overlaps_none_values(self):
        """None values should match."""
        coverage = TemporalCoverage(start=1800, end=1900)
        assert coverage.overlaps(None, None) is True


# =============================================================================
# SourceDefinition Tests
# =============================================================================


class TestSourceDefinition:
    """Tests for SourceDefinition class."""

    @pytest.fixture
    def belgian_source(self) -> SourceDefinition:
        """Create a Belgian source definition."""
        return SourceDefinition(
            id="belgian_state_archives",
            name="Belgian State Archives",
            url="https://search.arch.be",
            provider="belgian_archives",
            source_level=SourceLevel.PRIMARY,
            geographic=["Belgium", "Antwerp", "Brabant"],
            temporal=TemporalCoverage(start=1796, end=1912),
            record_types=["civil_registration", "birth", "marriage", "death"],
            ethnic_markers=[],
        )

    @pytest.fixture
    def cherokee_source(self) -> SourceDefinition:
        """Create a Cherokee source definition."""
        return SourceDefinition(
            id="dawes_rolls",
            name="Dawes Rolls",
            provider="nara",
            source_level=SourceLevel.PRIMARY,
            geographic=["Cherokee Nation", "Indian Territory", "Oklahoma"],
            temporal=TemporalCoverage(start=1898, end=1914),
            record_types=["enrollment"],
            ethnic_markers=["Cherokee", "Creek", "Choctaw"],
        )

    def test_matches_location_exact(self, belgian_source: SourceDefinition):
        """Exact location match should return True."""
        assert belgian_source.matches_location(["Belgium"]) is True

    def test_matches_location_partial(self, belgian_source: SourceDefinition):
        """Partial location match should return True."""
        assert belgian_source.matches_location(["Antwerp"]) is True

    def test_matches_location_case_insensitive(self, belgian_source: SourceDefinition):
        """Location matching should be case insensitive."""
        assert belgian_source.matches_location(["BELGIUM"]) is True
        assert belgian_source.matches_location(["belgium"]) is True

    def test_matches_location_no_match(self, belgian_source: SourceDefinition):
        """Non-matching location should return False."""
        assert belgian_source.matches_location(["France"]) is False

    def test_matches_location_empty_source(self):
        """Source with no geographic restriction should match any location."""
        source = SourceDefinition(id="global", name="Global Source", geographic=[])
        assert source.matches_location(["Anywhere"]) is True

    def test_matches_location_empty_query(self, belgian_source: SourceDefinition):
        """Empty location query should return True."""
        assert belgian_source.matches_location([]) is True

    def test_matches_time_year_in_range(self, belgian_source: SourceDefinition):
        """Year in range should return True."""
        assert belgian_source.matches_time(year=1850) is True

    def test_matches_time_year_out_of_range(self, belgian_source: SourceDefinition):
        """Year out of range should return False."""
        assert belgian_source.matches_time(year=1795) is False
        assert belgian_source.matches_time(year=1920) is False

    def test_matches_time_range_overlap(self, belgian_source: SourceDefinition):
        """Overlapping time range should return True."""
        assert belgian_source.matches_time(start=1800, end=1850) is True

    def test_matches_ethnicity_match(self, cherokee_source: SourceDefinition):
        """Matching ethnicity should return True."""
        assert cherokee_source.matches_ethnicity(["Cherokee"]) is True

    def test_matches_ethnicity_case_insensitive(self, cherokee_source: SourceDefinition):
        """Ethnicity matching should be case insensitive."""
        assert cherokee_source.matches_ethnicity(["cherokee"]) is True
        assert cherokee_source.matches_ethnicity(["CHEROKEE"]) is True

    def test_matches_ethnicity_no_match(self, cherokee_source: SourceDefinition):
        """Non-matching ethnicity should return False."""
        assert cherokee_source.matches_ethnicity(["Irish"]) is False

    def test_matches_ethnicity_empty_source(self, belgian_source: SourceDefinition):
        """Source with no ethnic markers should match any ethnicity."""
        assert belgian_source.matches_ethnicity(["Any"]) is True

    def test_from_dict(self):
        """Test creating SourceDefinition from dictionary."""
        data = {
            "name": "Test Source",
            "url": "https://example.com",
            "provider": "test",
            "source_level": "primary",
            "coverage": {
                "geographic": ["USA"],
                "temporal": {"start": 1800, "end": 1900},
            },
            "record_types": ["census"],
        }
        source = SourceDefinition.from_dict("test_source", data)

        assert source.id == "test_source"
        assert source.name == "Test Source"
        assert source.url == "https://example.com"
        assert source.source_level == SourceLevel.PRIMARY
        assert "USA" in source.geographic
        assert source.temporal.start == 1800
        assert source.temporal.end == 1900


# =============================================================================
# RoutingRule Tests
# =============================================================================


class TestRoutingRule:
    """Tests for RoutingRule class."""

    @pytest.fixture
    def belgian_rule(self) -> RoutingRule:
        """Create a Belgian routing rule."""
        return RoutingRule(
            name="belgian_civil",
            conditions={
                "geographic": ["Belgium"],
                "temporal": {"start": 1796, "end": 1912},
            },
            sources=["belgian_state_archives"],
            priority=1,
        )

    @pytest.fixture
    def cherokee_rule(self) -> RoutingRule:
        """Create a Cherokee routing rule."""
        return RoutingRule(
            name="cherokee_dawes",
            conditions={
                "ethnic_markers": ["Cherokee"],
                "temporal": {"start": 1898, "end": 1914},
            },
            sources=["dawes_rolls"],
            priority=1,
        )

    def test_matches_geographic(self, belgian_rule: RoutingRule):
        """Rule should match geographic conditions."""
        assert belgian_rule.matches(locations=["Belgium"], year=1850) is True

    def test_matches_geographic_partial(self, belgian_rule: RoutingRule):
        """Rule should match partial geographic conditions."""
        assert belgian_rule.matches(locations=["Antwerp, Belgium"], year=1850) is True

    def test_no_match_wrong_location(self, belgian_rule: RoutingRule):
        """Rule should not match wrong location."""
        assert belgian_rule.matches(locations=["France"], year=1850) is False

    def test_no_match_wrong_time(self, belgian_rule: RoutingRule):
        """Rule should not match wrong time period."""
        assert belgian_rule.matches(locations=["Belgium"], year=1795) is False

    def test_matches_ethnicity(self, cherokee_rule: RoutingRule):
        """Rule should match ethnic markers."""
        assert cherokee_rule.matches(ethnicities=["Cherokee"], year=1900) is True

    def test_no_match_missing_ethnicity(self, cherokee_rule: RoutingRule):
        """Rule should not match without required ethnicity."""
        assert cherokee_rule.matches(year=1900) is False

    def test_from_dict(self):
        """Test creating RoutingRule from dictionary."""
        data = {
            "name": "test_rule",
            "conditions": {
                "geographic": ["USA"],
                "temporal": {"start": 1800, "end": 1900},
            },
            "sources": ["source1", "source2"],
            "priority": 5,
        }
        rule = RoutingRule.from_dict(data)

        assert rule.name == "test_rule"
        assert rule.sources == ["source1", "source2"]
        assert rule.priority == 5


# =============================================================================
# SourceRegistry Tests
# =============================================================================


class TestSourceRegistry:
    """Tests for SourceRegistry class."""

    @pytest.fixture
    def registry(self) -> SourceRegistry:
        """Create a registry from the bundled sources.yaml."""
        return SourceRegistry()

    def test_registry_loads(self, registry: SourceRegistry):
        """Registry should load sources from YAML."""
        assert len(registry) > 0

    def test_get_source_by_id(self, registry: SourceRegistry):
        """Should retrieve source by ID."""
        source = registry.get_source("dawes_rolls")
        assert source is not None
        assert source.name == "Dawes Rolls (Final Rolls)"

    def test_get_source_not_found(self, registry: SourceRegistry):
        """Should return None for unknown source."""
        source = registry.get_source("nonexistent")
        assert source is None

    def test_get_multiple_sources(self, registry: SourceRegistry):
        """Should retrieve multiple sources by IDs."""
        sources = registry.get_sources(["dawes_rolls", "belgian_state_archives"])
        assert len(sources) == 2

    def test_all_sources(self, registry: SourceRegistry):
        """Should return all registered sources."""
        sources = registry.all_sources()
        assert len(sources) > 0
        assert all(isinstance(s, SourceDefinition) for s in sources)

    def test_find_sources_by_location(self, registry: SourceRegistry):
        """Should find sources by location."""
        sources = registry.find_sources(locations=["Belgium"])
        assert len(sources) > 0
        assert any("Belgian" in s.name for s in sources)

    def test_find_sources_by_year(self, registry: SourceRegistry):
        """Should find sources by year."""
        sources = registry.find_sources(year=1850)
        assert len(sources) > 0

    def test_find_sources_by_ethnicity(self, registry: SourceRegistry):
        """Should find sources by ethnicity."""
        sources = registry.find_sources(ethnicities=["Cherokee"])
        assert len(sources) > 0
        assert any("Cherokee" in str(s.ethnic_markers) for s in sources)

    def test_find_sources_by_source_level(self, registry: SourceRegistry):
        """Should filter by source level."""
        sources = registry.find_sources(source_level=SourceLevel.PRIMARY)
        assert len(sources) > 0
        assert all(s.source_level == SourceLevel.PRIMARY for s in sources)

    def test_find_sources_sorted_by_level(self, registry: SourceRegistry):
        """Sources should be sorted by source level (primary first)."""
        sources = registry.find_sources(locations=["United States"])
        if len(sources) > 1:
            levels = [s.source_level for s in sources]
            # Primary should come before tertiary
            primary_indices = [i for i, l in enumerate(levels) if l == SourceLevel.PRIMARY]
            tertiary_indices = [i for i, l in enumerate(levels) if l == SourceLevel.TERTIARY]
            if primary_indices and tertiary_indices:
                assert min(primary_indices) < max(tertiary_indices)

    def test_get_matching_rules_belgian(self, registry: SourceRegistry):
        """Should return matching rules for Belgian context."""
        rules = registry.get_matching_rules(locations=["Belgium"], year=1850)
        assert len(rules) > 0

    def test_get_matching_rules_cherokee(self, registry: SourceRegistry):
        """Should return matching rules for Cherokee context."""
        rules = registry.get_matching_rules(ethnicities=["Cherokee"], year=1900)
        assert len(rules) > 0

    def test_get_sources_by_rules(self, registry: SourceRegistry):
        """Should return sources recommended by matching rules."""
        sources = registry.get_sources_by_rules(
            locations=["Belgium"],
            year=1850,
        )
        assert len(sources) > 0

    def test_registry_repr(self, registry: SourceRegistry):
        """Registry should have informative repr."""
        repr_str = repr(registry)
        assert "SourceRegistry" in repr_str
        assert "sources" in repr_str
        assert "rules" in repr_str


class TestSourceRegistryFileNotFound:
    """Tests for registry with missing file."""

    def test_file_not_found_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            SourceRegistry(sources_path=tmp_path / "nonexistent.yaml")
