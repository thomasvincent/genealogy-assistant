"""Tests for core data models."""

from __future__ import annotations

import pytest
from datetime import datetime

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    ConclusionStatus,
    Event,
    Family,
    GenealogyDate,
    Name,
    Person,
    Place,
    Source,
    SourceLevel,
)


class TestGenealogyDate:
    """Tests for GenealogyDate model."""

    def test_exact_date_to_gedcom(self):
        """Test exact date formatting."""
        date = GenealogyDate(year=1895, month=3, day=15)
        assert date.to_gedcom() == "15 MAR 1895"

    def test_year_only_to_gedcom(self):
        """Test year-only date formatting."""
        date = GenealogyDate(year=1895)
        assert date.to_gedcom() == "1895"

    def test_year_month_to_gedcom(self):
        """Test year-month date formatting."""
        date = GenealogyDate(year=1895, month=3)
        assert date.to_gedcom() == "MAR 1895"

    def test_about_date_to_gedcom(self):
        """Test ABT modifier."""
        date = GenealogyDate(year=1895, modifier="ABT")
        assert date.to_gedcom() == "ABT 1895"

    def test_before_date_to_gedcom(self):
        """Test BEF modifier."""
        date = GenealogyDate(year=1900, modifier="BEF")
        assert date.to_gedcom() == "BEF 1900"

    def test_after_date_to_gedcom(self):
        """Test AFT modifier."""
        date = GenealogyDate(year=1890, modifier="AFT")
        assert date.to_gedcom() == "AFT 1890"

    def test_between_dates_to_gedcom(self):
        """Test BET...AND date range."""
        date = GenealogyDate(
            year=1890,
            modifier="BET",
            end_year=1895,
        )
        assert date.to_gedcom() == "BET 1890 AND 1895"

    def test_from_gedcom_exact(self):
        """Test parsing exact GEDCOM date."""
        date = GenealogyDate.from_gedcom("15 MAR 1895")
        assert date.year == 1895
        assert date.month == 3
        assert date.day == 15

    def test_from_gedcom_year_only(self):
        """Test parsing year-only GEDCOM date."""
        date = GenealogyDate.from_gedcom("1895")
        assert date.year == 1895
        assert date.month is None
        assert date.day is None

    def test_from_gedcom_with_modifier(self):
        """Test parsing GEDCOM date with modifier."""
        date = GenealogyDate.from_gedcom("ABT 1895")
        assert date.year == 1895
        assert date.modifier == "ABT"

    def test_to_datetime(self, sample_date: GenealogyDate):
        """Test conversion to Python datetime."""
        dt = sample_date.to_datetime()
        assert dt.year == 1895
        assert dt.month == 3
        assert dt.day == 15

    def test_to_datetime_year_only(self):
        """Test datetime conversion with year only."""
        date = GenealogyDate(year=1895)
        dt = date.to_datetime()
        assert dt.year == 1895
        assert dt.month == 1
        assert dt.day == 1


class TestPlace:
    """Tests for Place model."""

    def test_full_place_name(self, sample_place: Place):
        """Test place with all components."""
        assert sample_place.city == "Tervuren"
        assert sample_place.country == "Belgium"

    def test_place_from_string(self):
        """Test parsing place from comma-separated string."""
        place = Place.from_string("Detroit, Wayne, Michigan, USA")
        assert place.city == "Detroit"
        assert place.county == "Wayne"
        assert place.state == "Michigan"
        assert place.country == "USA"

    def test_place_from_string_short(self):
        """Test parsing short place name."""
        place = Place.from_string("Tervuren, Belgium")
        assert place.city == "Tervuren"
        assert place.country == "Belgium"


class TestPersonName:
    """Tests for PersonName model."""

    def test_full_name(self):
        """Test full name generation."""
        name = Name(
            surname="HERINCKX",
            given="Jean Joseph",
        )
        assert name.full_name() == "Jean Joseph HERINCKX"

    def test_full_name_with_prefix(self):
        """Test full name with prefix."""
        name = Name(
            surname="BERG",
            given="Johannes",
            prefix="van den",
        )
        assert name.full_name() == "Johannes van den BERG"

    def test_full_name_with_suffix(self):
        """Test full name with suffix."""
        name = Name(
            surname="SMITH",
            given="John",
            suffix="Jr.",
        )
        assert name.full_name() == "John SMITH Jr."

    def test_surname_variants(self):
        """Test surname variants."""
        name = Name(
            surname="HERINCKX",
            given="Jean",
            variants=["Herincx", "Herinck", "Herinxc"],
        )
        assert len(name.variants) == 3
        assert "Herincx" in name.variants


class TestPerson:
    """Tests for Person model."""

    def test_person_with_events(self, sample_person: Person):
        """Test person with birth and death events."""
        assert sample_person.id == "I001"
        assert sample_person.primary_name.surname == "HERINCKX"
        assert sample_person.birth is not None
        assert sample_person.death is not None

    def test_person_age_at_death(self, sample_person: Person):
        """Test calculating age at death."""
        # Born 1895, died 1962
        birth_year = sample_person.birth.date.year
        death_year = sample_person.death.date.year
        age = death_year - birth_year
        assert age == 67


class TestFamily:
    """Tests for Family model."""

    def test_family_members(self, sample_family: Family):
        """Test family with all members."""
        assert sample_family.id == "F001"
        assert sample_family.husband_id == "I001"
        assert sample_family.wife_id == "I002"
        assert len(sample_family.child_ids) == 2

    def test_family_marriage(self, sample_family: Family):
        """Test family marriage event."""
        assert sample_family.marriage is not None
        assert sample_family.marriage.date.year == 1890


class TestSource:
    """Tests for Source model."""

    def test_source_level(self, sample_source: Source):
        """Test source level assignment."""
        assert sample_source.source_level == SourceLevel.PRIMARY

    def test_source_hierarchy(self):
        """Test source level ordering."""
        assert SourceLevel.PRIMARY.value < SourceLevel.SECONDARY.value
        assert SourceLevel.SECONDARY.value < SourceLevel.TERTIARY.value


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_values(self):
        """Test confidence level values (IntEnum 1-5)."""
        assert ConfidenceLevel.GPS_COMPLETE.value == 5
        assert ConfidenceLevel.SPECULATIVE.value == 1
        assert ConfidenceLevel.WEAK.value == 2
        assert ConfidenceLevel.REASONABLE.value == 3
        assert ConfidenceLevel.STRONG.value == 4

    def test_confidence_ordering(self):
        """Test confidence levels can be compared."""
        levels = [
            ConfidenceLevel.SPECULATIVE,
            ConfidenceLevel.WEAK,
            ConfidenceLevel.REASONABLE,
            ConfidenceLevel.STRONG,
            ConfidenceLevel.GPS_COMPLETE,
        ]
        # Verify all levels are present
        assert len(levels) == 5
        # Verify ordering works (IntEnum supports comparison)
        assert ConfidenceLevel.SPECULATIVE < ConfidenceLevel.GPS_COMPLETE


class TestConclusionStatus:
    """Tests for ConclusionStatus enum."""

    def test_conclusion_statuses(self):
        """Test all conclusion status values (lowercase snake_case)."""
        assert ConclusionStatus.PROVEN.value == "proven"
        assert ConclusionStatus.LIKELY.value == "likely"
        assert ConclusionStatus.PROPOSED.value == "proposed"
        assert ConclusionStatus.DISPROVEN.value == "disproven"
        assert ConclusionStatus.UNSUBSTANTIATED.value == "unsubstantiated_family_lore"
