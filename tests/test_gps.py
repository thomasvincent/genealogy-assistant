"""Tests for GPS (Genealogical Proof Standard) enforcement."""

from __future__ import annotations

import pytest

from genealogy_assistant.core.gps import GenealogyProofStandard
from genealogy_assistant.core.models import (
    ConfidenceLevel,
    ConclusionStatus,
    ProofSummary,
    ResearchLog,
    ResearchLogEntry,
    SourceLevel,
)


class TestGenealogyProofStandard:
    """Tests for GPS enforcement."""

    @pytest.fixture
    def gps(self) -> GenealogyProofStandard:
        """Create GPS instance."""
        return GenealogyProofStandard()

    def test_validate_complete_proof(self, gps: GenealogyProofStandard, sample_proof_summary: ProofSummary):
        """Test validation of complete GPS proof."""
        result = gps.validate_proof(sample_proof_summary)

        assert result.is_valid
        assert len(result.issues) == 0

    def test_validate_incomplete_proof(self, gps: GenealogyProofStandard):
        """Test validation catches incomplete proof."""
        incomplete = ProofSummary(
            conclusion="Person X is the father of Person Y",
            status=ConclusionStatus.PROPOSED,
            confidence=ConfidenceLevel.WEAK,
            exhaustive_search=False,  # GPS Element 1 violated
            repositories_searched=[],
            sources=[],  # No sources - GPS Element 2 violated
            evidence=[],
            conflicts=[],
        )

        result = gps.validate_proof(incomplete)

        assert not result.is_valid
        assert len(result.issues) > 0
        # Should flag missing exhaustive search
        assert any("exhaustive" in i.lower() for i in result.issues)
        # Should flag missing sources
        assert any("source" in i.lower() for i in result.issues)

    def test_validate_unresolved_conflicts(self, gps: GenealogyProofStandard):
        """Test validation catches unresolved conflicts."""
        with_conflicts = ProofSummary(
            conclusion="Birth date is 15 March 1895",
            status=ConclusionStatus.PROPOSED,
            confidence=ConfidenceLevel.REASONABLE,
            exhaustive_search=True,
            repositories_searched=["Rijksarchief"],
            sources=["S001"],
            evidence=[{"source": "S001", "information": "Birth record"}],
            conflicts=[
                {
                    "description": "Death record says born 1894",
                    "resolution": None,  # Unresolved!
                }
            ],
        )

        result = gps.validate_proof(with_conflicts)

        # Should flag unresolved conflict
        assert any("conflict" in i.lower() or "unresolved" in i.lower() for i in result.issues)

    def test_required_searches_birth(self, gps: GenealogyProofStandard):
        """Test required search list for birth event."""
        searches = gps.get_required_searches("birth", "Belgium", 1895)

        # Should include Belgian civil registration
        assert any("civil" in s.lower() or "registration" in s.lower() for s in searches)
        # Should include church records as alternate
        assert any("church" in s.lower() or "parish" in s.lower() for s in searches)

    def test_required_searches_immigration(self, gps: GenealogyProofStandard):
        """Test required search list for immigration."""
        searches = gps.get_required_searches("immigration", "USA", 1910)

        # Should include ship manifests
        assert any("ship" in s.lower() or "passenger" in s.lower() or "manifest" in s.lower() for s in searches)
        # Should include naturalization
        assert any("naturalization" in s.lower() for s in searches)

    def test_required_searches_cherokee(self, gps: GenealogyProofStandard):
        """Test Cherokee roll requirements."""
        searches = gps.get_required_searches("tribal_enrollment", "Cherokee", 1900)

        # Should include Dawes Roll
        assert any("dawes" in s.lower() for s in searches)

    def test_source_hierarchy_enforcement(self, gps: GenealogyProofStandard):
        """Test source hierarchy rules."""
        # Primary source should be preferred
        primary = {"level": SourceLevel.PRIMARY, "type": "birth certificate"}
        secondary = {"level": SourceLevel.SECONDARY, "type": "published genealogy"}
        tertiary = {"level": SourceLevel.TERTIARY, "type": "ancestry tree"}

        # GPS: Primary > Secondary > Tertiary
        assert gps.compare_source_quality(primary, secondary) > 0
        assert gps.compare_source_quality(secondary, tertiary) > 0
        assert gps.compare_source_quality(primary, tertiary) > 0

    def test_tertiary_cannot_stand_alone(self, gps: GenealogyProofStandard):
        """Test that tertiary sources cannot stand alone."""
        tertiary_only = ProofSummary(
            conclusion="Family relationship exists",
            status=ConclusionStatus.PROPOSED,
            confidence=ConfidenceLevel.WEAK,
            exhaustive_search=False,
            repositories_searched=["Ancestry.com"],
            sources=["Ancestry Tree by user123"],
            evidence=[
                {"source": "Ancestry Tree", "quality": "Tertiary"}
            ],
            conflicts=[],
        )

        result = gps.validate_proof(tertiary_only)

        # Should flag tertiary-only evidence
        assert any("tertiary" in i.lower() or "primary" in i.lower() for i in result.issues)

    def test_evidence_correlation(self, gps: GenealogyProofStandard):
        """Test evidence correlation detection."""
        evidence_list = [
            {"source": "Birth cert", "info": "Born 15 Mar 1895", "place": "Tervuren"},
            {"source": "Census 1900", "info": "Age 5", "place": "Tervuren"},
            {"source": "Death cert", "info": "Born 1895", "place": "Tervuren"},
        ]

        correlation = gps.correlate_evidence(evidence_list)

        # Evidence should correlate (consistent dates and places)
        assert correlation.is_consistent
        assert correlation.confidence >= ConfidenceLevel.REASONABLE

    def test_evidence_conflict_detection(self, gps: GenealogyProofStandard):
        """Test detection of conflicting evidence."""
        conflicting_evidence = [
            {"source": "Birth cert", "info": "Born 15 Mar 1895"},
            {"source": "Death cert", "info": "Born 1894"},  # Conflict!
        ]

        correlation = gps.correlate_evidence(conflicting_evidence)

        # Should detect conflict
        assert not correlation.is_consistent or len(correlation.conflicts) > 0


class TestResearchLogValidation:
    """Tests for research log validation."""

    @pytest.fixture
    def gps(self) -> GenealogyProofStandard:
        """Create GPS instance."""
        return GenealogyProofStandard()

    def test_valid_research_log(self, gps: GenealogyProofStandard, sample_research_log: ResearchLog):
        """Test validation of complete research log."""
        result = gps.validate_research_log(sample_research_log)

        assert result.is_valid

    def test_empty_research_log(self, gps: GenealogyProofStandard):
        """Test validation catches empty log."""
        empty_log = ResearchLog(
            subject="Test Subject",
            objective="Find birth record",
            entries=[],
        )

        result = gps.validate_research_log(empty_log)

        assert not result.is_valid
        assert any("empty" in i.lower() or "no entries" in i.lower() for i in result.issues)

    def test_negative_results_documented(self, gps: GenealogyProofStandard):
        """Test that negative results are considered."""
        log_with_negatives = ResearchLog(
            subject="Test",
            objective="Find death record",
            entries=[
                ResearchLogEntry(
                    repository="County Clerk",
                    search_description="Death records 1900-1920",
                    result_summary="No record found",
                    negative_result=True,  # Important for GPS!
                ),
            ],
        )

        result = gps.validate_research_log(log_with_negatives)

        # Negative results should be valid and important for exhaustive research
        assert result.negative_results_count == 1


class TestConfidenceAssessment:
    """Tests for confidence level assessment."""

    @pytest.fixture
    def gps(self) -> GenealogyProofStandard:
        """Create GPS instance."""
        return GenealogyProofStandard()

    def test_high_confidence_criteria(self, gps: GenealogyProofStandard):
        """Test criteria for high confidence."""
        strong_case = {
            "primary_sources": 2,
            "secondary_sources": 1,
            "conflicts_resolved": True,
            "exhaustive_search": True,
            "direct_evidence": True,
        }

        confidence = gps.assess_confidence(strong_case)

        assert confidence in (ConfidenceLevel.STRONG, ConfidenceLevel.GPS_COMPLETE)

    def test_low_confidence_criteria(self, gps: GenealogyProofStandard):
        """Test criteria for low confidence."""
        weak_case = {
            "primary_sources": 0,
            "secondary_sources": 0,
            "tertiary_sources": 1,
            "conflicts_resolved": False,
            "exhaustive_search": False,
            "direct_evidence": False,
        }

        confidence = gps.assess_confidence(weak_case)

        assert confidence in (ConfidenceLevel.WEAK, ConfidenceLevel.SPECULATIVE)

    def test_gps_complete_requirements(self, gps: GenealogyProofStandard):
        """Test GPS Complete (5/5) requirements."""
        gps_complete_case = {
            "primary_sources": 3,
            "secondary_sources": 2,
            "conflicts_resolved": True,
            "exhaustive_search": True,
            "direct_evidence": True,
            "written_conclusion": True,
            "all_five_elements": True,
        }

        confidence = gps.assess_confidence(gps_complete_case)

        assert confidence == ConfidenceLevel.GPS_COMPLETE
