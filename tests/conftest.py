"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from genealogy_assistant.core.models import (
    Person,
    PersonName,
    Family,
    Event,
    Place,
    GenealogyDate,
    Source,
    Citation,
    SourceLevel,
    ConfidenceLevel,
    ConclusionStatus,
    ResearchLog,
    ResearchLogEntry,
    ProofSummary,
)


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_place() -> Place:
    """Create a sample place."""
    return Place(
        name="Tervuren, Brabant, Belgium",
        city="Tervuren",
        county="Brabant",
        state="Flemish Brabant",
        country="Belgium",
    )


@pytest.fixture
def sample_date() -> GenealogyDate:
    """Create a sample genealogy date."""
    return GenealogyDate(
        year=1895,
        month=3,
        day=15,
        modifier=None,
    )


@pytest.fixture
def sample_person(sample_place: Place, sample_date: GenealogyDate) -> Person:
    """Create a sample person."""
    person = Person(id="I001")
    person.primary_name = PersonName(
        surname="HERINCKX",
        given="Jean Joseph",
        prefix="",
        suffix="",
        variants=["Herinckx", "Herincx", "Herinck"],
    )
    person.birth = Event(
        event_type="BIRT",
        date=sample_date,
        place=sample_place,
    )
    person.death = Event(
        event_type="DEAT",
        date=GenealogyDate(year=1962, month=8, day=22),
        place=Place(name="Detroit, Wayne, Michigan, USA"),
    )
    return person


@pytest.fixture
def sample_family(sample_person: Person) -> Family:
    """Create a sample family."""
    wife = Person(id="I002")
    wife.primary_name = PersonName(surname="DE SMET", given="Marie Catherine")

    child1 = Person(id="I003")
    child1.primary_name = PersonName(surname="HERINCKX", given="Victor")

    child2 = Person(id="I004")
    child2.primary_name = PersonName(surname="HERINCKX", given="Frank")

    family = Family(
        id="F001",
        husband_id="I001",
        wife_id="I002",
        child_ids=["I003", "I004"],
    )
    family.marriage = Event(
        event_type="MARR",
        date=GenealogyDate(year=1890, month=6, day=12),
        place=Place(name="Overijse, Brabant, Belgium"),
    )

    return family


@pytest.fixture
def sample_source() -> Source:
    """Create a sample source."""
    return Source(
        id="S001",
        title="Tervuren Civil Registration - Births",
        author="Gemeente Tervuren",
        repository="Rijksarchief Leuven",
        source_type="vital_record",
        source_level=SourceLevel.PRIMARY,
        jurisdiction="Tervuren, Brabant, Belgium",
        date_range="1796-1912",
    )


@pytest.fixture
def sample_citation(sample_source: Source) -> Citation:
    """Create a sample citation."""
    return Citation(
        source_id="S001",
        page="Entry 45",
        detail="Birth of Jean Joseph Herinckx, 15 March 1895",
        quality="Primary, direct evidence",
    )


@pytest.fixture
def sample_research_log() -> ResearchLog:
    """Create a sample research log."""
    log = ResearchLog(
        subject="Herinckx Family Origins",
        objective="Identify parents of Jean Joseph Herinckx",
    )

    log.entries = [
        ResearchLogEntry(
            date=datetime(2024, 1, 15),
            repository="Rijksarchief Leuven",
            search_description="Search Tervuren birth registers 1890-1900",
            result_summary="Found birth record for Jean Joseph Herinckx, 15 Mar 1895",
            source_level=SourceLevel.PRIMARY,
            negative_result=False,
        ),
        ResearchLogEntry(
            date=datetime(2024, 1, 16),
            repository="FamilySearch",
            search_description="Search Belgium, Brabant, Civil Registration",
            result_summary="Found indexed birth record matching Rijksarchief record",
            source_level=SourceLevel.SECONDARY,
            negative_result=False,
        ),
        ResearchLogEntry(
            date=datetime(2024, 1, 17),
            repository="Geneanet",
            search_description="Search user trees for Herinckx in Tervuren",
            result_summary="Found tree by guynavez with matching family",
            source_level=SourceLevel.TERTIARY,
            negative_result=False,
        ),
    ]

    return log


@pytest.fixture
def sample_proof_summary(sample_research_log: ResearchLog) -> ProofSummary:
    """Create a sample proof summary."""
    return ProofSummary(
        conclusion="Jean Joseph Herinckx was born 15 March 1895 in Tervuren, Brabant, Belgium, to parents [father] and [mother].",
        status=ConclusionStatus.PROVEN,
        confidence=ConfidenceLevel.STRONG,
        exhaustive_search=True,
        repositories_searched=["Rijksarchief Leuven", "FamilySearch", "Geneanet"],
        sources=["S001", "S002", "S003"],
        evidence=[
            {"source": "S001", "information": "Birth record", "quality": "Primary"},
            {"source": "S002", "information": "Census record", "quality": "Primary"},
        ],
        conflicts=[],
    )


# =============================================================================
# GEDCOM Fixtures
# =============================================================================

@pytest.fixture
def sample_gedcom_content() -> str:
    """Sample minimal GEDCOM file content."""
    return """0 HEAD
1 SOUR Genealogy Assistant
2 VERS 0.1.0
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I001@ INDI
1 NAME Jean Joseph /HERINCKX/
1 BIRT
2 DATE 15 MAR 1895
2 PLAC Tervuren, Brabant, Belgium
1 DEAT
2 DATE 22 AUG 1962
2 PLAC Detroit, Wayne, Michigan, USA
1 FAMS @F001@
0 @I002@ INDI
1 NAME Marie Catherine /DE SMET/
1 FAMS @F001@
0 @I003@ INDI
1 NAME Victor /HERINCKX/
1 FAMC @F001@
0 @F001@ FAM
1 HUSB @I001@
1 WIFE @I002@
1 CHIL @I003@
1 MARR
2 DATE 12 JUN 1890
2 PLAC Overijse, Brabant, Belgium
0 TRLR
"""


@pytest.fixture
def sample_gedcom_file(tmp_path: Path, sample_gedcom_content: str) -> Path:
    """Create a temporary GEDCOM file."""
    gedcom_path = tmp_path / "test_family.ged"
    gedcom_path.write_text(sample_gedcom_content)
    return gedcom_path


# =============================================================================
# API Fixtures
# =============================================================================

@pytest.fixture
def mock_anthropic_response():
    """Mock response from Anthropic API."""
    class MockContent:
        text = """Based on GPS analysis:

## Extracted Facts
1. Jean Joseph Herinckx was born 15 March 1895 in Tervuren

## Confidence: 4

## Next Research Actions
- Obtain original birth certificate from Rijksarchief Leuven
- Search marriage records for parents
- Check census records for family unit

AI-assisted hypothesis generation was used. Conclusions rely solely on documented sources."""

    class MockResponse:
        content = [MockContent()]

    return MockResponse()
