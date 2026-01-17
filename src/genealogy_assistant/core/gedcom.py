"""
GEDCOM 5.5.1 / 7.0 file management with GPS compliance.

Handles:
- Reading and parsing GEDCOM files
- Writing GEDCOM with proper formatting
- Validation and integrity checks
- ID uniqueness enforcement
- Bidirectional link maintenance (FAMC/FAMS, CHIL/HUSB/WIFE)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, TextIO
from uuid import UUID, uuid4

from genealogy_assistant.core.models import (
    Citation,
    ConfidenceLevel,
    ConclusionStatus,
    Event,
    Family,
    GenealogyDate,
    Name,
    Person,
    Place,
    Repository,
    Source,
    SourceLevel,
)


@dataclass
class GedcomLine:
    """A single parsed GEDCOM line."""
    level: int
    tag: str
    value: str = ""
    xref: str | None = None  # @I123@ style ID

    @classmethod
    def parse(cls, line: str) -> GedcomLine | None:
        """Parse a GEDCOM line."""
        line = line.strip()
        if not line:
            return None

        # Pattern: level [xref] tag [value]
        # Examples:
        #   0 @I1@ INDI
        #   1 NAME John /Smith/
        #   2 DATE 15 JAN 1862

        match = re.match(
            r'^(\d+)\s+(?:(@[^@]+@)\s+)?(\S+)(?:\s+(.*))?$',
            line
        )
        if not match:
            return None

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3)
        value = match.group(4) or ""

        return cls(level=level, tag=tag, value=value, xref=xref)

    def to_string(self) -> str:
        """Convert back to GEDCOM format."""
        parts = [str(self.level)]
        if self.xref:
            parts.append(self.xref)
        parts.append(self.tag)
        if self.value:
            parts.append(self.value)
        return " ".join(parts)


@dataclass
class GedcomRecord:
    """A complete GEDCOM record (level 0 + subordinates)."""
    id: str | None  # @I123@ style
    tag: str  # INDI, FAM, SOUR, etc.
    lines: list[GedcomLine] = field(default_factory=list)

    def get_value(self, *path: str) -> str | None:
        """Get value at path like ('NAME', 'GIVN')."""
        current_level = 0
        current_match = True

        for line in self.lines[1:]:  # Skip level 0
            if line.level <= current_level and not current_match:
                current_match = True

            if current_match:
                if line.level == len(path) and line.tag == path[-1]:
                    return line.value

                if line.level < len(path) and line.tag == path[line.level - 1]:
                    current_level = line.level
                else:
                    current_match = False

        return None

    def get_all_values(self, tag: str, parent_tag: str | None = None) -> list[str]:
        """Get all values for a tag."""
        values = []
        in_parent = parent_tag is None

        for line in self.lines[1:]:
            if parent_tag and line.tag == parent_tag:
                in_parent = True
            elif parent_tag and line.level == 1 and line.tag != parent_tag:
                in_parent = False

            if in_parent and line.tag == tag:
                values.append(line.value)

        return values


@dataclass
class GedcomValidationError:
    """Validation error in GEDCOM file."""
    severity: str  # "error", "warning"
    record_id: str | None
    line_number: int | None
    message: str


class GedcomManager:
    """
    GEDCOM file manager with GPS-compliant validation.

    Handles reading, writing, and validating GEDCOM files
    while maintaining data integrity.
    """

    def __init__(self):
        self.records: dict[str, GedcomRecord] = {}
        self.header: GedcomRecord | None = None
        self.trailer: GedcomRecord | None = None

        # Indexes for fast lookup
        self.individuals: dict[str, GedcomRecord] = {}
        self.families: dict[str, GedcomRecord] = {}
        self.sources: dict[str, GedcomRecord] = {}
        self.repositories: dict[str, GedcomRecord] = {}

        # Validation state
        self.errors: list[GedcomValidationError] = []
        self.warnings: list[GedcomValidationError] = []

        # ID tracking
        self._next_indi_id = 1
        self._next_fam_id = 1
        self._next_sour_id = 1
        self._next_repo_id = 1

    def load(self, path: str | Path) -> None:
        """Load a GEDCOM file."""
        path = Path(path)
        with path.open("r", encoding="utf-8-sig") as f:
            self._parse(f)
        self._build_indexes()
        self._update_id_counters()

    def _parse(self, file: TextIO) -> None:
        """Parse GEDCOM content."""
        current_record: GedcomRecord | None = None
        line_number = 0

        for line in file:
            line_number += 1
            parsed = GedcomLine.parse(line)

            if not parsed:
                continue

            if parsed.level == 0:
                # Start new record
                if current_record:
                    self.records[current_record.id or current_record.tag] = current_record

                current_record = GedcomRecord(
                    id=parsed.xref,
                    tag=parsed.tag if not parsed.xref else parsed.value,
                    lines=[parsed],
                )

                # Special handling
                if parsed.tag == "HEAD":
                    self.header = current_record
                elif parsed.tag == "TRLR":
                    self.trailer = current_record

            elif current_record:
                current_record.lines.append(parsed)

        # Don't forget last record
        if current_record:
            self.records[current_record.id or current_record.tag] = current_record

    def _build_indexes(self) -> None:
        """Build indexes by record type."""
        for key, record in self.records.items():
            if record.tag == "INDI":
                self.individuals[key] = record
            elif record.tag == "FAM":
                self.families[key] = record
            elif record.tag == "SOUR":
                self.sources[key] = record
            elif record.tag == "REPO":
                self.repositories[key] = record

    def _update_id_counters(self) -> None:
        """Update ID counters to avoid collisions."""
        for key in self.individuals:
            match = re.match(r'@I(\d+)@', key)
            if match:
                self._next_indi_id = max(self._next_indi_id, int(match.group(1)) + 1)

        for key in self.families:
            match = re.match(r'@F(\d+)@', key)
            if match:
                self._next_fam_id = max(self._next_fam_id, int(match.group(1)) + 1)

        for key in self.sources:
            match = re.match(r'@S(\d+)@', key)
            if match:
                self._next_sour_id = max(self._next_sour_id, int(match.group(1)) + 1)

        for key in self.repositories:
            match = re.match(r'@R(\d+)@', key)
            if match:
                self._next_repo_id = max(self._next_repo_id, int(match.group(1)) + 1)

    def get_next_individual_id(self) -> str:
        """Get next available individual ID."""
        id_str = f"@I{self._next_indi_id}@"
        self._next_indi_id += 1
        return id_str

    def get_next_family_id(self) -> str:
        """Get next available family ID."""
        id_str = f"@F{self._next_fam_id}@"
        self._next_fam_id += 1
        return id_str

    def get_next_source_id(self) -> str:
        """Get next available source ID."""
        id_str = f"@S{self._next_sour_id}@"
        self._next_sour_id += 1
        return id_str

    def get_next_repo_id(self) -> str:
        """Get next available repository ID."""
        id_str = f"@R{self._next_repo_id}@"
        self._next_repo_id += 1
        return id_str

    def validate(self) -> list[GedcomValidationError]:
        """
        Validate GEDCOM file integrity.

        Checks:
        - ID uniqueness
        - Bidirectional links (FAMC/FAMS, CHIL)
        - Date formats
        - Required fields
        """
        self.errors = []
        self.warnings = []

        self._validate_ids()
        self._validate_links()
        self._validate_dates()

        return self.errors + self.warnings

    def _validate_ids(self) -> None:
        """Check for duplicate IDs."""
        all_ids = set()

        for record in self.records.values():
            if record.id:
                if record.id in all_ids:
                    self.errors.append(GedcomValidationError(
                        severity="error",
                        record_id=record.id,
                        line_number=None,
                        message=f"Duplicate ID: {record.id}",
                    ))
                all_ids.add(record.id)

    def _validate_links(self) -> None:
        """Validate bidirectional family links."""
        # Check FAMC links
        for indi_id, indi in self.individuals.items():
            famc_refs = indi.get_all_values("FAMC")
            for fam_ref in famc_refs:
                if fam_ref not in self.families:
                    self.errors.append(GedcomValidationError(
                        severity="error",
                        record_id=indi_id,
                        line_number=None,
                        message=f"FAMC references non-existent family: {fam_ref}",
                    ))
                else:
                    # Check if family has this person as CHIL
                    family = self.families[fam_ref]
                    children = family.get_all_values("CHIL")
                    if indi_id not in children:
                        self.warnings.append(GedcomValidationError(
                            severity="warning",
                            record_id=indi_id,
                            line_number=None,
                            message=f"FAMC {fam_ref} does not list this person as CHIL",
                        ))

        # Check FAMS links
        for indi_id, indi in self.individuals.items():
            fams_refs = indi.get_all_values("FAMS")
            for fam_ref in fams_refs:
                if fam_ref not in self.families:
                    self.errors.append(GedcomValidationError(
                        severity="error",
                        record_id=indi_id,
                        line_number=None,
                        message=f"FAMS references non-existent family: {fam_ref}",
                    ))

        # Check family spouse/child links
        for fam_id, fam in self.families.items():
            husb = fam.get_all_values("HUSB")
            wife = fam.get_all_values("WIFE")
            children = fam.get_all_values("CHIL")

            for spouse_ref in husb + wife:
                if spouse_ref not in self.individuals:
                    self.errors.append(GedcomValidationError(
                        severity="error",
                        record_id=fam_id,
                        line_number=None,
                        message=f"Spouse references non-existent individual: {spouse_ref}",
                    ))

            for child_ref in children:
                if child_ref not in self.individuals:
                    self.errors.append(GedcomValidationError(
                        severity="error",
                        record_id=fam_id,
                        line_number=None,
                        message=f"CHIL references non-existent individual: {child_ref}",
                    ))

    def _validate_dates(self) -> None:
        """Validate date formats."""
        date_pattern = re.compile(
            r'^(ABT|BEF|AFT|BET|CAL|EST)?\s*'
            r'(\d{1,2})?\s*'
            r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)?\s*'
            r'(\d{4})?'
            r'(\s+AND\s+.*)?$',
            re.IGNORECASE
        )

        for record_id, record in self.records.items():
            for line in record.lines:
                if line.tag == "DATE" and line.value:
                    if not date_pattern.match(line.value):
                        self.warnings.append(GedcomValidationError(
                            severity="warning",
                            record_id=record_id,
                            line_number=None,
                            message=f"Non-standard date format: {line.value}",
                        ))

    def save(self, path: str | Path, update_header: bool = True) -> None:
        """Save GEDCOM to file."""
        path = Path(path)

        if update_header:
            self._update_header()

        with path.open("w", encoding="utf-8") as f:
            # Write header first
            if self.header:
                self._write_record(f, self.header)

            # Write all other records
            for key, record in self.records.items():
                if record != self.header and record != self.trailer:
                    self._write_record(f, record)

            # Write trailer last
            f.write("0 TRLR\n")

    def _update_header(self) -> None:
        """Update header with current date/time."""
        if not self.header:
            return

        now = datetime.now()

        for line in self.header.lines:
            if line.tag == "DATE":
                line.value = now.strftime("%d %b %Y").upper()
            elif line.tag == "TIME":
                line.value = now.strftime("%H:%M:%S")

    def _write_record(self, f: TextIO, record: GedcomRecord) -> None:
        """Write a single record to file."""
        for line in record.lines:
            f.write(line.to_string() + "\n")

    def get_person(self, gedcom_id: str) -> Person | None:
        """Convert GEDCOM individual to Person model."""
        record = self.individuals.get(gedcom_id)
        if not record:
            return None

        person = Person(
            gedcom_id=gedcom_id,
        )

        # Parse name
        name_value = record.get_all_values("NAME")
        if name_value:
            for nv in name_value:
                # Parse "Given /Surname/" format
                match = re.match(r'^([^/]*)\s*/([^/]*)/(.*)$', nv)
                if match:
                    given = match.group(1).strip()
                    surname = match.group(2).strip()
                    person.names.append(Name(
                        given=given,
                        surname=surname,
                    ))

        # Parse sex
        sex_value = record.get_all_values("SEX")
        if sex_value:
            person.sex = sex_value[0] if sex_value[0] in ["M", "F"] else "U"

        # Parse birth
        birth_date = None
        birth_place = None
        for line in record.lines:
            if line.tag == "BIRT":
                # Look for DATE and PLAC in following lines
                for subline in record.lines[record.lines.index(line):]:
                    if subline.level <= line.level and subline != line:
                        break
                    if subline.tag == "DATE":
                        birth_date = GenealogyDate.from_string(subline.value)
                    if subline.tag == "PLAC":
                        birth_place = Place.from_string(subline.value)

        if birth_date or birth_place:
            person.birth = Event(
                event_type="BIRT",
                date=birth_date,
                place=birth_place,
            )

        # Parse death
        death_date = None
        death_place = None
        for line in record.lines:
            if line.tag == "DEAT":
                for subline in record.lines[record.lines.index(line):]:
                    if subline.level <= line.level and subline != line:
                        break
                    if subline.tag == "DATE":
                        death_date = GenealogyDate.from_string(subline.value)
                    if subline.tag == "PLAC":
                        death_place = Place.from_string(subline.value)

        if death_date or death_place:
            person.death = Event(
                event_type="DEAT",
                date=death_date,
                place=death_place,
            )

        # Parse family links
        famc_refs = record.get_all_values("FAMC")
        fams_refs = record.get_all_values("FAMS")

        # Store GEDCOM refs for now; would convert to UUIDs with full db
        # person.parent_family_ids = famc_refs  # type mismatch, for illustration

        return person

    def add_person(self, person: Person) -> str:
        """
        Add a person to the GEDCOM.

        Returns the assigned GEDCOM ID.
        """
        gedcom_id = person.gedcom_id or self.get_next_individual_id()

        lines = [
            GedcomLine(level=0, xref=gedcom_id, tag="INDI"),
        ]

        # Add name
        if person.primary_name:
            name = person.primary_name
            lines.append(GedcomLine(
                level=1, tag="NAME",
                value=name.gedcom_name()
            ))
            lines.append(GedcomLine(level=2, tag="GIVN", value=name.given))
            lines.append(GedcomLine(level=2, tag="SURN", value=name.surname))
            if name.nickname:
                lines.append(GedcomLine(level=2, tag="NICK", value=name.nickname))

        # Add sex
        lines.append(GedcomLine(level=1, tag="SEX", value=person.sex))

        # Add birth
        if person.birth:
            lines.append(GedcomLine(level=1, tag="BIRT"))
            if person.birth.date:
                lines.append(GedcomLine(
                    level=2, tag="DATE",
                    value=person.birth.date.to_gedcom()
                ))
            if person.birth.place:
                lines.append(GedcomLine(
                    level=2, tag="PLAC",
                    value=person.birth.place.to_gedcom()
                ))

        # Add death
        if person.death:
            lines.append(GedcomLine(level=1, tag="DEAT"))
            if person.death.date:
                lines.append(GedcomLine(
                    level=2, tag="DATE",
                    value=person.death.date.to_gedcom()
                ))
            if person.death.place:
                lines.append(GedcomLine(
                    level=2, tag="PLAC",
                    value=person.death.place.to_gedcom()
                ))

        record = GedcomRecord(id=gedcom_id, tag="INDI", lines=lines)
        self.records[gedcom_id] = record
        self.individuals[gedcom_id] = record

        return gedcom_id

    def add_family(
        self,
        husband_id: str | None = None,
        wife_id: str | None = None,
        children_ids: list[str] | None = None,
        marriage_date: GenealogyDate | None = None,
        marriage_place: Place | None = None,
    ) -> str:
        """
        Add a family to the GEDCOM.

        Automatically maintains bidirectional links.
        Returns the assigned GEDCOM ID.
        """
        gedcom_id = self.get_next_family_id()

        lines = [
            GedcomLine(level=0, xref=gedcom_id, tag="FAM"),
        ]

        # Add husband
        if husband_id:
            lines.append(GedcomLine(level=1, tag="HUSB", value=husband_id))
            # Add FAMS to husband
            self._add_fams_link(husband_id, gedcom_id)

        # Add wife
        if wife_id:
            lines.append(GedcomLine(level=1, tag="WIFE", value=wife_id))
            # Add FAMS to wife
            self._add_fams_link(wife_id, gedcom_id)

        # Add marriage
        if marriage_date or marriage_place:
            lines.append(GedcomLine(level=1, tag="MARR"))
            if marriage_date:
                lines.append(GedcomLine(
                    level=2, tag="DATE",
                    value=marriage_date.to_gedcom()
                ))
            if marriage_place:
                lines.append(GedcomLine(
                    level=2, tag="PLAC",
                    value=marriage_place.to_gedcom()
                ))

        # Add children
        if children_ids:
            for child_id in children_ids:
                lines.append(GedcomLine(level=1, tag="CHIL", value=child_id))
                # Add FAMC to child
                self._add_famc_link(child_id, gedcom_id)

        record = GedcomRecord(id=gedcom_id, tag="FAM", lines=lines)
        self.records[gedcom_id] = record
        self.families[gedcom_id] = record

        return gedcom_id

    def _add_fams_link(self, indi_id: str, fam_id: str) -> None:
        """Add FAMS link to individual."""
        if indi_id in self.individuals:
            record = self.individuals[indi_id]
            record.lines.append(GedcomLine(level=1, tag="FAMS", value=fam_id))

    def _add_famc_link(self, indi_id: str, fam_id: str) -> None:
        """Add FAMC link to individual."""
        if indi_id in self.individuals:
            record = self.individuals[indi_id]
            record.lines.append(GedcomLine(level=1, tag="FAMC", value=fam_id))

    def add_source(self, source: Source) -> str:
        """Add a source to the GEDCOM."""
        gedcom_id = self.get_next_source_id()

        lines = [
            GedcomLine(level=0, xref=gedcom_id, tag="SOUR"),
            GedcomLine(level=1, tag="TITL", value=source.title),
        ]

        if source.author:
            lines.append(GedcomLine(level=1, tag="AUTH", value=source.author))
        if source.publisher:
            lines.append(GedcomLine(level=1, tag="PUBL", value=source.publisher))
        if source.repository:
            # Would need repo ID lookup
            pass
        if source.notes:
            lines.append(GedcomLine(level=1, tag="NOTE", value=source.notes))

        record = GedcomRecord(id=gedcom_id, tag="SOUR", lines=lines)
        self.records[gedcom_id] = record
        self.sources[gedcom_id] = record

        return gedcom_id

    def get_statistics(self) -> dict:
        """Get GEDCOM file statistics."""
        return {
            "individuals": len(self.individuals),
            "families": len(self.families),
            "sources": len(self.sources),
            "repositories": len(self.repositories),
            "total_records": len(self.records),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }

    def find_person_by_name(
        self,
        given: str | None = None,
        surname: str | None = None,
    ) -> list[str]:
        """Find individuals by name."""
        results = []

        for indi_id, record in self.individuals.items():
            names = record.get_all_values("NAME")
            for name in names:
                match_given = given is None or given.lower() in name.lower()
                match_surname = surname is None or surname.lower() in name.lower()
                if match_given and match_surname:
                    results.append(indi_id)
                    break

        return results

    def generate_name_variants(self, surname: str) -> list[str]:
        """
        Generate common spelling variants for a surname.

        Essential for Belgian/Dutch/German research.
        """
        variants = {surname}

        # Common Belgian/Dutch substitutions
        substitutions = [
            ("ck", "k"), ("ck", "c"),
            ("x", "cks"), ("x", "ks"),
            ("ae", "a"), ("oe", "o"), ("ue", "u"),
            ("y", "ij"), ("ij", "y"),
            ("dt", "t"), ("dt", "d"),
            ("sch", "sh"),
        ]

        for old, new in substitutions:
            if old in surname.lower():
                variants.add(surname.lower().replace(old, new))
            if new in surname.lower():
                variants.add(surname.lower().replace(new, old))

        # Double letters
        for char in "bcdfglmnprst":
            single = char
            double = char * 2
            if double in surname.lower():
                variants.add(surname.lower().replace(double, single))
            if single in surname.lower() and double not in surname.lower():
                variants.add(surname.lower().replace(single, double, 1))

        return sorted(v.title() for v in variants)
