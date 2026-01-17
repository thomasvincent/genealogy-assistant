"""
Citation formatting for genealogical sources.

Implements Evidence Explained style citations for genealogical records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from genealogy_assistant.core.models import Source, Citation, SourceLevel


class CitationStyle(Enum):
    """Citation formatting styles."""
    EVIDENCE_EXPLAINED = "evidence_explained"  # Elizabeth Shown Mills
    CHICAGO = "chicago"  # Chicago Manual of Style
    SIMPLE = "simple"  # Basic citation


@dataclass
class CitationFormatter:
    """
    Formats genealogical source citations.

    Follows Evidence Explained conventions for genealogical citations.
    """

    style: CitationStyle = CitationStyle.EVIDENCE_EXPLAINED

    def format_source(self, source: Source) -> str:
        """Format a source as a full citation."""
        if self.style == CitationStyle.EVIDENCE_EXPLAINED:
            return self._format_ee(source)
        elif self.style == CitationStyle.CHICAGO:
            return self._format_chicago(source)
        else:
            return self._format_simple(source)

    def format_citation(self, citation: Citation, source: Source) -> str:
        """Format a citation (reference to specific info in source)."""
        base = self.format_source(source)

        if citation.page:
            base += f", p. {citation.page}"
        if citation.detail:
            base += f"; {citation.detail}"

        return base

    def _format_ee(self, source: Source) -> str:
        """Format in Evidence Explained style."""
        parts = []

        # Determine source type and format accordingly
        if source.source_type == "vital_record":
            parts.extend(self._format_vital_record_ee(source))
        elif source.source_type == "census":
            parts.extend(self._format_census_ee(source))
        elif source.source_type == "church_record":
            parts.extend(self._format_church_record_ee(source))
        elif source.source_type == "newspaper":
            parts.extend(self._format_newspaper_ee(source))
        elif source.source_type == "book":
            parts.extend(self._format_book_ee(source))
        elif source.source_type == "online_database":
            parts.extend(self._format_online_database_ee(source))
        else:
            parts.extend(self._format_generic_ee(source))

        return ", ".join(filter(None, parts)) + "."

    def _format_vital_record_ee(self, source: Source) -> list[str]:
        """Format vital record (birth, death, marriage) EE style."""
        parts = []

        # Jurisdiction
        if source.jurisdiction:
            parts.append(source.jurisdiction)

        # Record type
        if source.title:
            parts.append(f'"{source.title}"')

        # Date/year range
        if source.date_range:
            parts.append(f"({source.date_range})")

        # Specific entry
        if source.entry_info:
            parts.append(source.entry_info)

        # Repository
        if source.repository:
            repo_str = source.repository
            if source.call_number:
                repo_str += f", {source.call_number}"
            parts.append(repo_str)

        # Access info (for microfilm, FHL, etc.)
        if source.film_number:
            parts.append(f"FHL microfilm {source.film_number}")

        return parts

    def _format_census_ee(self, source: Source) -> list[str]:
        """Format census record EE style."""
        parts = []

        # Year and type
        if source.date_range:
            parts.append(f"{source.date_range} U.S. census")

        # Jurisdiction (county, state)
        if source.jurisdiction:
            parts.append(source.jurisdiction)

        # Enumeration district/page
        if source.entry_info:
            parts.append(source.entry_info)

        # NARA info
        if source.nara_series:
            parts.append(f"NARA microfilm publication {source.nara_series}")
            if source.nara_roll:
                parts.append(f"roll {source.nara_roll}")

        # Accessed via
        if source.accessed_via:
            parts.append(f"accessed via {source.accessed_via}")
            if source.access_date:
                parts.append(f"({source.access_date})")

        return parts

    def _format_church_record_ee(self, source: Source) -> list[str]:
        """Format church record EE style."""
        parts = []

        # Church name
        if source.church_name:
            parts.append(source.church_name)

        # Location
        if source.jurisdiction:
            parts.append(source.jurisdiction)

        # Record type
        if source.title:
            parts.append(source.title)

        # Date range
        if source.date_range:
            parts.append(f"({source.date_range})")

        # Specific entry
        if source.entry_info:
            parts.append(source.entry_info)

        # Repository
        if source.repository:
            parts.append(source.repository)

        return parts

    def _format_newspaper_ee(self, source: Source) -> list[str]:
        """Format newspaper article EE style."""
        parts = []

        # Article title (if any)
        if source.article_title:
            parts.append(f'"{source.article_title}"')

        # Newspaper name
        if source.title:
            parts.append(f"*{source.title}*")

        # Place of publication
        if source.publication_place:
            parts.append(f"({source.publication_place})")

        # Date
        if source.publication_date:
            parts.append(source.publication_date)

        # Page/column
        if source.page:
            parts.append(f"p. {source.page}")
        if source.column:
            parts.append(f"col. {source.column}")

        return parts

    def _format_book_ee(self, source: Source) -> list[str]:
        """Format book EE style."""
        parts = []

        # Author
        if source.author:
            parts.append(source.author)

        # Title
        if source.title:
            parts.append(f"*{source.title}*")

        # Publication info
        pub_parts = []
        if source.publication_place:
            pub_parts.append(source.publication_place)
        if source.publisher:
            pub_parts.append(source.publisher)
        if source.publication_date:
            pub_parts.append(source.publication_date)
        if pub_parts:
            parts.append(f"({', '.join(pub_parts)})")

        return parts

    def _format_online_database_ee(self, source: Source) -> list[str]:
        """Format online database EE style."""
        parts = []

        # Database name
        if source.title:
            parts.append(f'"{source.title}"')

        # Website/provider
        if source.provider:
            parts.append(f"*{source.provider}*")

        # URL
        if source.url:
            parts.append(f"({source.url})")

        # Access date
        if source.access_date:
            parts.append(f": accessed {source.access_date}")

        # Original source cited
        if source.original_source:
            parts.append(f"citing {source.original_source}")

        return parts

    def _format_generic_ee(self, source: Source) -> list[str]:
        """Format generic source EE style."""
        parts = []

        if source.author:
            parts.append(source.author)
        if source.title:
            parts.append(f'"{source.title}"')
        if source.publisher:
            parts.append(source.publisher)
        if source.repository:
            parts.append(source.repository)
        if source.url:
            parts.append(source.url)

        return parts

    def _format_chicago(self, source: Source) -> str:
        """Format in Chicago Manual of Style."""
        parts = []

        if source.author:
            parts.append(source.author + ".")

        if source.title:
            parts.append(f"*{source.title}*.")

        pub_parts = []
        if source.publication_place:
            pub_parts.append(source.publication_place)
        if source.publisher:
            pub_parts.append(source.publisher)
        if source.publication_date:
            pub_parts.append(source.publication_date)
        if pub_parts:
            parts.append(", ".join(pub_parts) + ".")

        if source.url:
            parts.append(source.url)

        return " ".join(parts)

    def _format_simple(self, source: Source) -> str:
        """Format in simple style."""
        parts = []

        if source.title:
            parts.append(source.title)
        if source.author:
            parts.append(f"by {source.author}")
        if source.repository:
            parts.append(f"at {source.repository}")
        if source.url:
            parts.append(f"[{source.url}]")

        return ", ".join(parts)

    def format_footnote(self, source: Source, citation: Citation, note_num: int) -> str:
        """Format as a footnote with number."""
        citation_text = self.format_citation(citation, source)
        return f"{note_num}. {citation_text}"

    def format_bibliography_entry(self, source: Source) -> str:
        """Format for bibliography/source list."""
        # For bibliography, author comes first (Last, First)
        if self.style == CitationStyle.EVIDENCE_EXPLAINED:
            return self._format_bibliography_ee(source)
        else:
            return self.format_source(source)

    def _format_bibliography_ee(self, source: Source) -> str:
        """Format bibliography entry EE style."""
        parts = []

        # Author (Last, First format)
        if source.author:
            # Try to reverse name order
            author = source.author
            if " " in author and "," not in author:
                name_parts = author.rsplit(" ", 1)
                if len(name_parts) == 2:
                    author = f"{name_parts[1]}, {name_parts[0]}"
            parts.append(author + ".")

        # Title
        if source.title:
            parts.append(f"*{source.title}*.")

        # Publication info
        pub_parts = []
        if source.publication_place:
            pub_parts.append(source.publication_place)
        if source.publisher:
            pub_parts.append(source.publisher)
        if source.publication_date:
            pub_parts.append(source.publication_date)
        if pub_parts:
            parts.append(", ".join(pub_parts) + ".")

        return " ".join(parts)

    def categorize_source_level(self, source: Source) -> SourceLevel:
        """
        Categorize source by GPS source hierarchy.

        Returns the appropriate source level based on source characteristics.
        """
        source_type = source.source_type or ""

        # Primary sources: created at or near the time of event
        primary_types = [
            "vital_record", "civil_registration", "parish_register",
            "census", "military_record", "naturalization",
            "probate", "land_deed", "tax_record",
        ]
        if source_type in primary_types:
            return SourceLevel.PRIMARY

        # Secondary sources: derived from primary sources
        secondary_types = [
            "published_genealogy", "county_history", "biography",
            "compiled_record", "transcription", "abstract",
        ]
        if source_type in secondary_types:
            return SourceLevel.SECONDARY

        # Tertiary sources: indexes, databases, user-submitted
        tertiary_types = [
            "online_tree", "index", "database_entry",
            "message_board", "findagrave", "ancestry_tree",
        ]
        if source_type in tertiary_types:
            return SourceLevel.TERTIARY

        # Check for online database indicators
        if source.provider and any(
            p in source.provider.lower()
            for p in ["ancestry", "familysearch", "myheritage", "findmypast"]
        ):
            # Online databases that are transcriptions are secondary
            if source.original_source:
                return SourceLevel.SECONDARY
            # User trees are tertiary
            if "tree" in source_type.lower():
                return SourceLevel.TERTIARY

        # Default to secondary if unclear
        return SourceLevel.SECONDARY

    def validate_citation(self, citation: Citation, source: Source) -> list[str]:
        """
        Validate a citation for GPS compliance.

        Returns list of issues found.
        """
        issues = []

        # Must have a source
        if not source:
            issues.append("Citation must reference a source")
            return issues

        # Source should have title
        if not source.title:
            issues.append("Source should have a title")

        # Check for repository or access info
        if not source.repository and not source.url:
            issues.append("Source should specify repository or access location")

        # Check for date information
        if not source.date_range and not source.publication_date:
            issues.append("Source should specify a date or date range")

        # For online sources, need access date
        if source.url and not source.access_date:
            issues.append("Online sources should include access date")

        # For tertiary sources, need original source
        level = self.categorize_source_level(source)
        if level == SourceLevel.TERTIARY and not source.original_source:
            issues.append("Tertiary sources should cite the original source")

        return issues


def format_source_list(sources: list[Source], style: CitationStyle = CitationStyle.EVIDENCE_EXPLAINED) -> str:
    """Format a list of sources as a bibliography."""
    formatter = CitationFormatter(style=style)

    entries = []
    for source in sources:
        entry = formatter.format_bibliography_entry(source)
        level = formatter.categorize_source_level(source)
        entries.append((level, entry))

    # Sort by level (primary first) then alphabetically
    entries.sort(key=lambda x: (x[0].value, x[1]))

    lines = ["# Sources", ""]

    current_level = None
    for level, entry in entries:
        if level != current_level:
            lines.append(f"## {level.value} Sources")
            lines.append("")
            current_level = level
        lines.append(f"- {entry}")

    return "\n".join(lines)
