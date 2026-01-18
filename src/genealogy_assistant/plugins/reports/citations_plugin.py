"""Citations plugin for Semantic Kernel."""

from __future__ import annotations

from typing import Annotated

from semantic_kernel.functions import kernel_function


class CitationsPlugin:
    """
    Citation formatting plugin following Evidence Explained standards.

    Generates properly formatted genealogical source citations.
    """

    @kernel_function(
        name="format_vital_record_citation",
        description="Format a citation for a vital record (birth, marriage, death)",
    )
    def format_vital_record_citation(
        self,
        record_type: Annotated[str, "Type of record: 'birth', 'marriage', or 'death'"],
        jurisdiction: Annotated[str, "Jurisdiction (e.g., 'Tervuren, Brabant, Belgium')"],
        date: Annotated[str, "Date of the record"],
        person_name: Annotated[str, "Name of the person in the record"],
        repository: Annotated[str, "Where the record is held"],
        access_info: Annotated[str | None, "How the record was accessed"] = None,
    ) -> str:
        """
        Format a citation for a vital record.

        Uses Evidence Explained format for civil registration.
        """
        citation = f'{jurisdiction}, {record_type.title()} Register, {date}, entry for {person_name}; {repository}'

        if access_info:
            citation += f"; accessed via {access_info}"

        citation += "."

        return f"**Citation:**\n{citation}"

    @kernel_function(
        name="format_census_citation",
        description="Format a citation for a census record",
    )
    def format_census_citation(
        self,
        year: Annotated[int, "Census year"],
        country: Annotated[str, "Country (e.g., 'United States', 'Belgium')"],
        location: Annotated[str, "Specific location in census"],
        household_head: Annotated[str, "Name of household head"],
        page_info: Annotated[str, "Page, dwelling, family numbers"],
        repository: Annotated[str, "Repository holding the record"],
        film_number: Annotated[str | None, "Microfilm number if applicable"] = None,
    ) -> str:
        """
        Format a citation for a census record.

        Uses Evidence Explained format for census records.
        """
        citation = f'{year} {country} Census, {location}, {page_info}, household of {household_head}; {repository}'

        if film_number:
            citation += f", film {film_number}"

        citation += "."

        return f"**Citation:**\n{citation}"

    @kernel_function(
        name="format_online_database_citation",
        description="Format a citation for an online database or website",
    )
    def format_online_database_citation(
        self,
        database_name: Annotated[str, "Name of the database (e.g., 'FamilySearch', 'Ancestry')"],
        record_title: Annotated[str, "Title or description of the record"],
        url: Annotated[str, "URL of the record"],
        access_date: Annotated[str, "Date accessed"],
        original_source: Annotated[str | None, "Original source if this is a derivative"] = None,
    ) -> str:
        """
        Format a citation for an online database.

        Notes: Tertiary sources should cite the original source.
        """
        citation = f'"{record_title}," {database_name}, {url}, accessed {access_date}'

        if original_source:
            citation += f"; citing {original_source}"

        citation += "."

        classification = "TERTIARY" if not original_source else "SECONDARY (citing primary)"

        return f"**Citation ({classification}):**\n{citation}"

    @kernel_function(
        name="format_parish_register_citation",
        description="Format a citation for a church/parish register",
    )
    def format_parish_register_citation(
        self,
        parish: Annotated[str, "Parish name"],
        diocese: Annotated[str, "Diocese or denomination"],
        record_type: Annotated[str, "Type: 'baptism', 'marriage', 'burial'"],
        date: Annotated[str, "Date of the entry"],
        person_name: Annotated[str, "Name(s) in the record"],
        repository: Annotated[str, "Archive or repository"],
        volume_page: Annotated[str | None, "Volume and page if known"] = None,
    ) -> str:
        """
        Format a citation for a parish register.

        Parish registers are PRIMARY sources for events before civil registration.
        """
        citation = f'{parish} ({diocese}), {record_type.title()} Register'

        if volume_page:
            citation += f', {volume_page}'

        citation += f', {date}, entry for {person_name}; {repository}.'

        return f"**Citation (PRIMARY):**\n{citation}"

    @kernel_function(
        name="classify_source",
        description="Classify a source as primary, secondary, or tertiary",
    )
    def classify_source(
        self,
        source_description: Annotated[str, "Description of the source"],
    ) -> str:
        """
        Classify a source type and explain why.

        Returns classification with explanation.
        """
        source_lower = source_description.lower()

        # Primary indicators
        primary_keywords = [
            "civil registration", "birth certificate", "marriage certificate",
            "death certificate", "parish register", "baptism", "burial",
            "census", "original", "military record", "naturalization",
            "passenger list", "will", "probate", "deed", "court record",
        ]

        # Secondary indicators
        secondary_keywords = [
            "transcription", "abstract", "published genealogy", "county history",
            "compiled", "derivative", "extract", "translation",
        ]

        # Tertiary indicators
        tertiary_keywords = [
            "ancestry tree", "familysearch tree", "user tree", "findagrave",
            "wikipedia", "geni", "myheritage tree", "index", "database",
            "geneanet tree", "hint", "suggestion",
        ]

        for keyword in primary_keywords:
            if keyword in source_lower:
                return f"""**Classification: PRIMARY**

Source: {source_description}

Reason: This appears to be a primary source ('{keyword}' detected).
Primary sources were created at or near the time of the event by someone
with direct knowledge.

Note: Verify you have the original or a faithful image, not just an index."""

        for keyword in secondary_keywords:
            if keyword in source_lower:
                return f"""**Classification: SECONDARY**

Source: {source_description}

Reason: This appears to be a secondary source ('{keyword}' detected).
Secondary sources are derived from primary sources and may contain
transcription errors or interpretations.

Note: Attempt to locate the original primary source for verification."""

        for keyword in tertiary_keywords:
            if keyword in source_lower:
                return f"""**Classification: TERTIARY**

Source: {source_description}

Reason: This appears to be a tertiary source ('{keyword}' detected).
Tertiary sources include indexes, databases, and user-submitted trees.

WARNING: NEVER rely solely on tertiary sources. They must be verified
against primary sources. User trees are particularly unreliable."""

        return f"""**Classification: UNKNOWN**

Source: {source_description}

Unable to automatically classify this source.

To classify manually, consider:
- When was it created relative to the event?
- Who created it? (Eyewitness, recorder, compiler?)
- Is it original or derived?

Generally:
- PRIMARY: Created at/near event time by knowledgeable party
- SECONDARY: Compiled from or interpreting primary sources
- TERTIARY: Indexes, databases, user trees"""

    @kernel_function(
        name="generate_bibliography_entry",
        description="Generate a bibliography entry for a source",
    )
    def generate_bibliography_entry(
        self,
        author: Annotated[str | None, "Author name(s)"] = None,
        title: Annotated[str, "Title of the work"] = "",
        publication_info: Annotated[str | None, "Publisher, place, date"] = None,
        url: Annotated[str | None, "URL if online"] = None,
        access_date: Annotated[str | None, "Date accessed if online"] = None,
    ) -> str:
        """
        Generate a bibliography entry.

        Uses modified Evidence Explained format for bibliography.
        """
        parts = []

        if author:
            parts.append(f"{author}.")

        if title:
            parts.append(f"*{title}*.")

        if publication_info:
            parts.append(f"{publication_info}.")

        if url:
            parts.append(f"<{url}>")
            if access_date:
                parts.append(f"(accessed {access_date}).")

        entry = " ".join(parts)

        return f"**Bibliography Entry:**\n{entry}"
