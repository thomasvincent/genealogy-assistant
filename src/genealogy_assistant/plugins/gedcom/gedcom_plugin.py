"""GEDCOM file operations plugin for Semantic Kernel."""

from __future__ import annotations

from typing import Annotated

from semantic_kernel.functions import kernel_function

from genealogy_assistant.core.gedcom import GedcomManager


class GedcomPlugin:
    """
    GEDCOM file operations plugin.

    Wraps GedcomManager for reading, writing, and validating GEDCOM files.
    """

    def __init__(self):
        """Initialize the GEDCOM plugin."""
        self._manager = GedcomManager()
        self._loaded_file: str | None = None

    @kernel_function(
        name="load_gedcom",
        description="Load a GEDCOM file and return statistics about its contents",
    )
    def load_gedcom(
        self,
        file_path: Annotated[str, "Path to the GEDCOM file to load"],
    ) -> str:
        """
        Load a GEDCOM file.

        Returns statistics about individuals, families, and sources.
        """
        self._manager = GedcomManager()  # Reset manager
        self._manager.load(file_path)
        self._loaded_file = file_path

        stats = self._manager.stats()
        return f"""GEDCOM loaded: {file_path}
Individuals: {stats['individuals']}
Families: {stats['families']}
Sources: {stats['sources']}
Repositories: {stats['repositories']}"""

    @kernel_function(
        name="find_person",
        description="Find persons in the loaded GEDCOM by name",
    )
    def find_person(
        self,
        surname: Annotated[str | None, "Surname to search for"] = None,
        given_name: Annotated[str | None, "Given name to search for"] = None,
    ) -> str:
        """
        Find persons in the loaded GEDCOM matching the criteria.

        Returns formatted list of matching individuals.
        """
        if not self._loaded_file:
            return "No GEDCOM file loaded. Use load_gedcom first."

        persons = self._manager.find_persons(
            surname=surname,
            given_name=given_name,
        )

        if not persons:
            return f"No persons found matching surname='{surname}', given_name='{given_name}'"

        lines = [f"Found {len(persons)} matching persons:\n"]
        for person in persons:
            name = person.primary_name.full_name() if person.primary_name else "Unknown"
            lines.append(f"- {person.gedcom_id}: {name}")

            if person.birth and person.birth.date:
                lines.append(f"  Birth: {person.birth.date.to_gedcom()}")
                if person.birth.place:
                    lines.append(f"  Place: {person.birth.place.name}")

            if person.death and person.death.date:
                lines.append(f"  Death: {person.death.date.to_gedcom()}")

            lines.append("")

        return "\n".join(lines)

    @kernel_function(
        name="get_person",
        description="Get detailed information about a specific person by ID",
    )
    def get_person(
        self,
        person_id: Annotated[str, "GEDCOM ID of the person (e.g., 'I001' or '@I001@')"],
    ) -> str:
        """
        Get detailed information about a specific person.

        Returns all available data for the person.
        """
        if not self._loaded_file:
            return "No GEDCOM file loaded. Use load_gedcom first."

        person = self._manager.get_person(person_id)
        if not person:
            return f"Person {person_id} not found"

        lines = [f"Person: {person_id}"]

        if person.primary_name:
            lines.append(f"Name: {person.primary_name.full_name()}")
            if person.primary_name.variants:
                lines.append(f"Variants: {', '.join(person.primary_name.variants)}")

        lines.append(f"Sex: {person.sex}")

        if person.birth:
            birth_info = "Birth: "
            if person.birth.date:
                birth_info += person.birth.date.to_gedcom()
            if person.birth.place:
                birth_info += f" at {person.birth.place.name}"
            lines.append(birth_info)

        if person.death:
            death_info = "Death: "
            if person.death.date:
                death_info += person.death.date.to_gedcom()
            if person.death.place:
                death_info += f" at {person.death.place.name}"
            lines.append(death_info)

        return "\n".join(lines)

    @kernel_function(
        name="get_family",
        description="Get information about a family unit by ID",
    )
    def get_family(
        self,
        family_id: Annotated[str, "GEDCOM ID of the family (e.g., 'F001' or '@F001@')"],
    ) -> str:
        """
        Get information about a family unit.

        Returns spouses, marriage info, and children.
        """
        if not self._loaded_file:
            return "No GEDCOM file loaded. Use load_gedcom first."

        family = self._manager.get_family(family_id)
        if not family:
            return f"Family {family_id} not found"

        lines = [f"Family: {family_id}"]

        if family.husband_id:
            husband = self._manager.get_person(family.husband_id)
            name = husband.primary_name.full_name() if husband and husband.primary_name else "Unknown"
            lines.append(f"Husband: {family.husband_id} - {name}")

        if family.wife_id:
            wife = self._manager.get_person(family.wife_id)
            name = wife.primary_name.full_name() if wife and wife.primary_name else "Unknown"
            lines.append(f"Wife: {family.wife_id} - {name}")

        if family.marriage:
            marriage_info = "Marriage: "
            if family.marriage.date:
                marriage_info += family.marriage.date.to_gedcom()
            if family.marriage.place:
                marriage_info += f" at {family.marriage.place.name}"
            lines.append(marriage_info)

        if family.child_ids:
            lines.append(f"Children ({len(family.child_ids)}):")
            for child_id in family.child_ids:
                child = self._manager.get_person(child_id)
                name = child.primary_name.full_name() if child and child.primary_name else "Unknown"
                lines.append(f"  - {child_id}: {name}")

        return "\n".join(lines)

    @kernel_function(
        name="validate_gedcom",
        description="Validate the loaded GEDCOM file for errors and warnings",
    )
    def validate_gedcom(self) -> str:
        """
        Validate the loaded GEDCOM file.

        Checks for duplicate IDs, orphan references, date formats, etc.
        """
        if not self._loaded_file:
            return "No GEDCOM file loaded. Use load_gedcom first."

        issues = self._manager.validate()

        if not issues:
            return "GEDCOM validation passed with no issues."

        errors = [i for i in issues if i.startswith("ERROR")]
        warnings = [i for i in issues if i.startswith("WARNING")]

        lines = ["GEDCOM Validation Results:\n"]
        lines.append(f"Errors: {len(errors)}")
        lines.append(f"Warnings: {len(warnings)}\n")

        if errors:
            lines.append("ERRORS:")
            for error in errors:
                lines.append(f"  {error}")
            lines.append("")

        if warnings:
            lines.append("WARNINGS:")
            for warning in warnings:
                lines.append(f"  {warning}")

        return "\n".join(lines)

    @kernel_function(
        name="generate_surname_variants",
        description="Generate spelling variants for a surname (useful for Belgian/Dutch names)",
    )
    def generate_surname_variants(
        self,
        surname: Annotated[str, "The surname to generate variants for"],
    ) -> str:
        """
        Generate common spelling variants for a surname.

        Essential for Belgian/Dutch/German research where spellings varied.
        """
        variants = self._manager.generate_surname_variants(surname)

        lines = [f"Surname variants for '{surname}':\n"]
        for variant in variants:
            lines.append(f"  - {variant}")

        lines.append(f"\nTotal: {len(variants)} variants")
        lines.append("\nTip: Search for all variants when researching historical records.")

        return "\n".join(lines)

    @kernel_function(
        name="get_statistics",
        description="Get statistics about the loaded GEDCOM file",
    )
    def get_statistics(self) -> str:
        """Get statistics about the loaded GEDCOM file."""
        if not self._loaded_file:
            return "No GEDCOM file loaded. Use load_gedcom first."

        stats = self._manager.stats()
        return f"""GEDCOM Statistics for {self._loaded_file}:
- Individuals: {stats['individuals']}
- Families: {stats['families']}
- Sources: {stats['sources']}
- Repositories: {stats['repositories']}
- Total Records: {stats['total_records']}
- Validation Errors: {stats['errors']}
- Validation Warnings: {stats['warnings']}"""
