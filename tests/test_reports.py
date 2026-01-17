"""Tests for report generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    ConclusionStatus,
    Family,
    Name,
    Person,
    ProofSummary,
    ResearchLog,
    Source,
    SourceLevel,
)
from genealogy_assistant.reports.proof import ProofSummaryReport
from genealogy_assistant.reports.research_log import ResearchLogReport
from genealogy_assistant.reports.family_group import FamilyGroupSheet
from genealogy_assistant.reports.pedigree import PedigreeChart
from genealogy_assistant.reports.citations import CitationFormatter, CitationStyle


class TestProofSummaryReport:
    """Tests for proof summary report generation."""

    def test_generate_markdown(
        self, sample_person: Person, sample_proof_summary: ProofSummary, sample_research_log: ResearchLog
    ):
        """Test Markdown report generation."""
        report = ProofSummaryReport(
            title="Proof of Herinckx Birth",
            researcher="Test Researcher",
            subject=sample_person,
            research_question="When and where was Jean Joseph Herinckx born?",
            proof_summary=sample_proof_summary,
            research_log=sample_research_log,
            format="markdown",
        )

        output = report.generate()

        # Check structure
        assert "# Proof of Herinckx Birth" in output
        assert "## Research Question" in output
        assert "## GPS Compliance" in output
        assert "## Evidence Summary" in output
        assert "## Conclusion" in output

        # Check content
        assert "Test Researcher" in output
        assert "Jean Joseph HERINCKX" in output or "HERINCKX" in output

    def test_generate_html(self, sample_person: Person, sample_proof_summary: ProofSummary):
        """Test HTML report generation."""
        report = ProofSummaryReport(
            title="Test Report",
            researcher="Tester",
            subject=sample_person,
            proof_summary=sample_proof_summary,
            format="html",
        )

        output = report.generate()

        # Check HTML structure
        assert "<!DOCTYPE html>" in output
        assert "<html" in output
        assert "<title>" in output
        assert "</html>" in output

    def test_gps_checklist(self, sample_proof_summary: ProofSummary):
        """Test GPS checklist generation."""
        report = ProofSummaryReport(
            title="Test",
            researcher="Test",
            proof_summary=sample_proof_summary,
            format="markdown",
        )

        output = report.generate()

        # All 5 GPS elements should be checked
        assert "Exhaustive Research" in output or "exhaustive" in output.lower()
        assert "Citations" in output or "citation" in output.lower()
        assert "Analysis" in output or "analysis" in output.lower()
        assert "Conflict" in output or "conflict" in output.lower()
        assert "Conclusion" in output or "conclusion" in output.lower()

    def test_save_report(self, sample_proof_summary: ProofSummary, tmp_path: Path):
        """Test saving report to file."""
        report = ProofSummaryReport(
            title="Test Report",
            researcher="Test",
            proof_summary=sample_proof_summary,
        )

        output_path = tmp_path / "report.md"
        report.save(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "# Test Report" in content


class TestResearchLogReport:
    """Tests for research log report generation."""

    def test_generate_markdown(self, sample_research_log: ResearchLog):
        """Test Markdown research log generation."""
        report = ResearchLogReport(
            research_log=sample_research_log,
            title="Herinckx Research Log",
            researcher="Test",
            format="markdown",
        )

        output = report.generate()

        # Check structure
        assert "# Herinckx Research Log" in output
        assert "## Summary" in output
        assert "## Detailed Log" in output

        # Check table header
        assert "| Date |" in output
        assert "| Repository |" in output

    def test_generate_csv(self, sample_research_log: ResearchLog):
        """Test CSV export."""
        report = ResearchLogReport(
            research_log=sample_research_log,
            format="csv",
        )

        output = report.generate()

        # Check CSV header
        assert "Date,Repository" in output
        # Check data rows
        lines = output.strip().split("\n")
        assert len(lines) > 1  # Header + data

    def test_negative_results_section(self, sample_research_log: ResearchLog):
        """Test negative results documentation."""
        report = ResearchLogReport(
            research_log=sample_research_log,
            format="markdown",
        )

        output = report.generate()

        # Should have negative results section
        assert "## Negative Results" in output


class TestFamilyGroupSheet:
    """Tests for family group sheet generation."""

    def test_generate_markdown(self, sample_person: Person, sample_family: Family):
        """Test family group sheet generation."""
        wife = Person()
        wife.names.append(Name(surname="DE SMET", given="Marie Catherine"))

        child = Person()
        child.names.append(Name(surname="HERINCKX", given="Victor"))

        sheet = FamilyGroupSheet(
            family=sample_family,
            husband=sample_person,
            wife=wife,
            children=[child],
            title="Herinckx-De Smet Family",
            researcher="Test",
            format="markdown",
        )

        output = sheet.generate()

        # Check structure
        assert "# Herinckx-De Smet Family" in output
        assert "## Husband" in output
        assert "## Wife" in output
        assert "## Children" in output

        # Check content
        assert "Jean Joseph" in output or "HERINCKX" in output
        assert "DE SMET" in output
        assert "Victor" in output

    def test_marriage_section(self, sample_person: Person, sample_family: Family):
        """Test marriage information."""
        sheet = FamilyGroupSheet(
            family=sample_family,
            husband=sample_person,
            format="markdown",
        )

        output = sheet.generate()

        assert "## Marriage" in output
        assert "1890" in output  # Marriage year


class TestPedigreeChart:
    """Tests for pedigree chart generation."""

    def test_generate_markdown(self, sample_person: Person):
        """Test pedigree chart generation."""
        father = Person()
        father.names.append(Name(surname="HERINCKX", given="Pierre"))

        mother = Person()
        mother.names.append(Name(surname="JANSSENS", given="Maria"))

        chart = PedigreeChart(
            subject=sample_person,
            generations=3,
            format="markdown",
        )
        chart.add_ancestor(2, father)
        chart.add_ancestor(3, mother)

        output = chart.generate()

        # Check structure
        assert "Ahnentafel" in output
        assert "## Pedigree Tree" in output

        # Check content
        assert "Jean Joseph" in output or "HERINCKX" in output
        assert "Pierre" in output
        assert "JANSSENS" in output or "Maria" in output

    def test_ahnentafel_numbering(self, sample_person: Person):
        """Test Ahnentafel numbering system."""
        chart = PedigreeChart(
            subject=sample_person,
            generations=4,
        )

        # Subject = 1
        assert chart.ancestors.get(1) == sample_person

        # Father should be 2 * subject
        father = Person()
        father.names.append(Name(surname="HERINCKX", given="Father"))
        chart.add_ancestor(2, father)

        assert chart.get_father(1) == father

        # Mother should be 2 * subject + 1
        mother = Person()
        mother.names.append(Name(surname="TEST", given="Mother"))
        chart.add_ancestor(3, mother)

        assert chart.get_mother(1) == mother

    def test_generate_mermaid(self, sample_person: Person):
        """Test Mermaid diagram generation."""
        chart = PedigreeChart(
            subject=sample_person,
            generations=2,
            format="mermaid",
        )

        output = chart.generate()

        assert "```mermaid" in output
        assert "graph TD" in output


class TestCitationFormatter:
    """Tests for citation formatting."""

    def test_format_vital_record(self):
        """Test vital record citation formatting."""
        source = Source(
            id="S001",
            title="Birth Register",
            source_type="vital_record",
            jurisdiction="Tervuren, Brabant, Belgium",
            date_range="1895",
            repository="Rijksarchief Leuven",
        )

        formatter = CitationFormatter(style=CitationStyle.EVIDENCE_EXPLAINED)
        citation = formatter.format_source(source)

        assert "Tervuren" in citation
        assert "1895" in citation or "Birth" in citation

    def test_format_census(self):
        """Test census citation formatting."""
        source = Source(
            id="S002",
            title="Population Schedule",
            source_type="census",
            date_range="1900",
            jurisdiction="Wayne County, Michigan",
            nara_series="T623",
            nara_roll="1234",
        )

        formatter = CitationFormatter(style=CitationStyle.EVIDENCE_EXPLAINED)
        citation = formatter.format_source(source)

        assert "1900" in citation
        assert "census" in citation.lower() or "Wayne" in citation

    def test_format_online_database(self):
        """Test online database citation formatting."""
        source = Source(
            id="S003",
            title="Belgium, Brabant, Civil Registration",
            source_type="online_database",
            provider="FamilySearch",
            url="https://familysearch.org/...",
            access_date="15 January 2024",
            original_source="Tervuren Civil Registration",
        )

        formatter = CitationFormatter(style=CitationStyle.EVIDENCE_EXPLAINED)
        citation = formatter.format_source(source)

        assert "FamilySearch" in citation
        assert "accessed" in citation.lower() or "2024" in citation

    def test_categorize_source_level(self):
        """Test source level categorization."""
        formatter = CitationFormatter()

        # Primary source
        primary = Source(id="1", source_type="vital_record")
        assert formatter.categorize_source_level(primary) == SourceLevel.PRIMARY

        # Secondary source
        secondary = Source(id="2", source_type="published_genealogy")
        assert formatter.categorize_source_level(secondary) == SourceLevel.SECONDARY

        # Tertiary source
        tertiary = Source(id="3", source_type="online_tree")
        assert formatter.categorize_source_level(tertiary) == SourceLevel.TERTIARY

    def test_validate_citation(self, sample_source: Source, sample_citation):
        """Test citation validation."""
        formatter = CitationFormatter()

        issues = formatter.validate_citation(sample_citation, sample_source)

        # Well-formed citation should have few/no issues
        # (depends on how complete sample_source is)
        assert isinstance(issues, list)

    def test_bibliography_format(self, sample_source: Source):
        """Test bibliography entry formatting."""
        formatter = CitationFormatter()

        entry = formatter.format_bibliography_entry(sample_source)

        assert len(entry) > 0
        assert sample_source.title in entry or "Tervuren" in entry
