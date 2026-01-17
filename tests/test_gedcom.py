"""Tests for GEDCOM file management."""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_assistant.core.gedcom import GedcomManager


class TestGedcomManager:
    """Tests for GedcomManager class."""

    def test_load_gedcom(self, sample_gedcom_file: Path):
        """Test loading a GEDCOM file."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        stats = manager.stats()
        assert stats["individuals"] >= 3
        assert stats["families"] >= 1

    def test_find_person_by_surname(self, sample_gedcom_file: Path):
        """Test finding persons by surname."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        results = manager.find_persons(surname="HERINCKX")
        assert len(results) >= 2  # Jean Joseph and Victor

    def test_find_person_by_given_name(self, sample_gedcom_file: Path):
        """Test finding persons by given name."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        results = manager.find_persons(given_name="Victor")
        assert len(results) >= 1

    def test_validate_gedcom(self, sample_gedcom_file: Path):
        """Test GEDCOM validation."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        issues = manager.validate()
        # Sample GEDCOM should be valid
        errors = [i for i in issues if i.startswith("ERROR")]
        assert len(errors) == 0

    def test_get_person_by_id(self, sample_gedcom_file: Path):
        """Test retrieving person by ID."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        person = manager.get_person("I001")
        assert person is not None
        assert person.primary_name.surname == "HERINCKX"

    def test_get_family_by_id(self, sample_gedcom_file: Path):
        """Test retrieving family by ID."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        family = manager.get_family("F001")
        assert family is not None
        assert family.husband_id == "I001"

    def test_stats(self, sample_gedcom_file: Path):
        """Test GEDCOM statistics."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        stats = manager.stats()
        assert "individuals" in stats
        assert "families" in stats
        assert stats["individuals"] >= 1
        assert stats["families"] >= 1

    def test_save_gedcom(self, sample_gedcom_file: Path, tmp_path: Path):
        """Test saving a GEDCOM file."""
        manager = GedcomManager()
        manager.load(str(sample_gedcom_file))

        output_path = tmp_path / "output.ged"
        manager.save(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "0 HEAD" in content
        assert "0 TRLR" in content


class TestGedcomValidation:
    """Tests for GEDCOM validation."""

    def test_validate_missing_required_fields(self, tmp_path: Path):
        """Test validation catches missing required fields."""
        # GEDCOM without proper header
        bad_gedcom = """0 @I001@ INDI
1 NAME Test /PERSON/
0 TRLR
"""
        gedcom_path = tmp_path / "bad.ged"
        gedcom_path.write_text(bad_gedcom)

        manager = GedcomManager()
        manager.load(str(gedcom_path))
        issues = manager.validate()

        # Should flag missing/malformed header
        assert len(issues) > 0

    def test_validate_orphan_family_reference(self, tmp_path: Path):
        """Test validation catches orphan references."""
        # Person references non-existent family
        orphan_gedcom = """0 HEAD
1 SOUR Test
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
0 @I001@ INDI
1 NAME Test /PERSON/
1 FAMS @F999@
0 TRLR
"""
        gedcom_path = tmp_path / "orphan.ged"
        gedcom_path.write_text(orphan_gedcom)

        manager = GedcomManager()
        manager.load(str(gedcom_path))
        issues = manager.validate()

        # Should warn about orphan reference
        warnings = [i for i in issues if "F999" in i or "orphan" in i.lower()]
        assert len(warnings) > 0


class TestSurnameVariants:
    """Tests for surname variant generation."""

    def test_belgian_surname_variants(self):
        """Test Belgian/Dutch surname variants."""
        manager = GedcomManager()
        variants = manager.generate_surname_variants("HERINCKX")

        assert "HERINCKX" in variants
        assert "Herinckx" in variants
        # Should include spelling variations
        assert any("Herincx" in v or "Herinck" in v for v in variants)

    def test_prefix_surname_variants(self):
        """Test surnames with prefixes."""
        manager = GedcomManager()
        variants = manager.generate_surname_variants("VAN DEN BERG")

        assert "VAN DEN BERG" in variants
        # Should include variations with/without prefix
        assert any("BERG" in v for v in variants)
        assert any("Vandenberg" in v or "van den Berg" in v for v in variants)

    def test_simple_surname(self):
        """Test simple surname without variations."""
        manager = GedcomManager()
        variants = manager.generate_surname_variants("SMITH")

        assert "SMITH" in variants
        assert "Smith" in variants
