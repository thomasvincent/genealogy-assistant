"""
Base classes for genealogy search providers.

Defines the interface that all search providers must implement
for consistent access across different genealogy databases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from genealogy_assistant.core.models import (
    GenealogyDate,
    Place,
    SourceLevel,
)


class RecordType(str, Enum):
    """Types of genealogical records."""
    BIRTH = "birth"
    DEATH = "death"
    MARRIAGE = "marriage"
    BURIAL = "burial"
    CENSUS = "census"
    IMMIGRATION = "immigration"
    EMIGRATION = "emigration"
    MILITARY = "military"
    PROBATE = "probate"
    LAND = "land"
    CHURCH = "church"
    CIVIL = "civil"
    NEWSPAPER = "newspaper"
    OTHER = "other"


class Region(str, Enum):
    """Geographic regions for search filtering."""
    BELGIUM = "belgium"
    NETHERLANDS = "netherlands"
    GERMANY = "germany"
    FRANCE = "france"
    IRELAND = "ireland"
    SCOTLAND = "scotland"
    ENGLAND = "england"
    WALES = "wales"
    CHANNEL_ISLANDS = "channel_islands"
    USA = "usa"
    CANADA = "canada"
    WORLDWIDE = "worldwide"


@dataclass
class SearchQuery:
    """
    Query parameters for genealogy searches.

    Supports common search criteria across providers.
    """
    # Name components
    given_name: str | None = None
    surname: str | None = None
    maiden_name: str | None = None

    # Surname variants to search
    surname_variants: list[str] = field(default_factory=list)

    # Date ranges
    birth_year: int | None = None
    birth_year_range: int = 5  # +/- years
    death_year: int | None = None
    death_year_range: int = 5
    event_year: int | None = None
    event_year_range: int = 5

    # Place filters
    birth_place: str | None = None
    death_place: str | None = None
    residence_place: str | None = None
    event_place: str | None = None

    # Region filter
    region: Region | None = None
    country: str | None = None

    # Record type filter
    record_types: list[RecordType] = field(default_factory=list)

    # Relationship filters
    father_name: str | None = None
    mother_name: str | None = None
    spouse_name: str | None = None

    # Pagination
    page: int = 1
    page_size: int = 50

    # Provider-specific options
    options: dict[str, Any] = field(default_factory=dict)

    def get_all_surname_variants(self) -> list[str]:
        """Get primary surname plus all variants."""
        variants = []
        if self.surname:
            variants.append(self.surname)
        variants.extend(self.surname_variants)
        return list(set(variants))


@dataclass
class SearchResult:
    """
    A single search result from a genealogy database.

    Normalized structure across all providers.
    """
    id: UUID = field(default_factory=uuid4)
    provider: str = ""  # e.g., "familysearch", "geneanet"

    # Record identifiers
    record_id: str = ""  # Provider's record ID
    collection_id: str | None = None
    film_number: str | None = None

    # Person information
    given_name: str = ""
    surname: str = ""
    sex: str | None = None  # "M", "F", or None

    # Life events
    birth_date: GenealogyDate | None = None
    birth_place: Place | None = None
    death_date: GenealogyDate | None = None
    death_place: Place | None = None

    # Event (for non-vital records)
    event_type: RecordType | None = None
    event_date: GenealogyDate | None = None
    event_place: Place | None = None

    # Family
    father_name: str | None = None
    mother_name: str | None = None
    spouse_name: str | None = None

    # Source information
    record_title: str = ""
    collection_name: str | None = None
    source_level: SourceLevel = SourceLevel.SECONDARY
    has_image: bool = False
    image_url: str | None = None

    # Links
    record_url: str | None = None

    # Match quality
    relevance_score: float = 0.0  # 0-1

    # Raw data for debugging
    raw_data: dict = field(default_factory=dict)

    def to_citation_text(self) -> str:
        """Generate citation text for this result."""
        parts = [self.collection_name or self.record_title]

        if self.film_number:
            parts.append(f"Film {self.film_number}")
        if self.record_id:
            parts.append(f"Record {self.record_id}")

        return "; ".join(parts)


@dataclass
class SearchResponse:
    """Response from a search operation."""
    query: SearchQuery
    provider: str
    results: list[SearchResult] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 50
    has_more: bool = False
    error: str | None = None
    search_time_ms: float = 0.0


class SearchProvider(ABC):
    """
    Abstract base class for genealogy search providers.

    All search providers (FamilySearch, Geneanet, etc.) must
    implement this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'FamilySearch')."""
        pass

    @property
    @abstractmethod
    def code(self) -> str:
        """Provider code (e.g., 'familysearch')."""
        pass

    @property
    def source_level(self) -> SourceLevel:
        """Default source level for this provider's records."""
        return SourceLevel.SECONDARY

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Execute a search query.

        Args:
            query: Search parameters

        Returns:
            SearchResponse with results
        """
        pass

    @abstractmethod
    async def get_record(self, record_id: str) -> SearchResult | None:
        """
        Get a specific record by ID.

        Args:
            record_id: Provider's record identifier

        Returns:
            SearchResult or None if not found
        """
        pass

    async def search_person(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
    ) -> SearchResponse:
        """Convenience method for person search."""
        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=birth_place,
        )
        return await self.search(query)

    async def search_birth(
        self,
        surname: str,
        given_name: str | None = None,
        year: int | None = None,
        place: str | None = None,
    ) -> SearchResponse:
        """Search for birth records."""
        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            birth_year=year,
            birth_place=place,
            record_types=[RecordType.BIRTH],
        )
        return await self.search(query)

    async def search_death(
        self,
        surname: str,
        given_name: str | None = None,
        year: int | None = None,
        place: str | None = None,
    ) -> SearchResponse:
        """Search for death records."""
        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            death_year=year,
            death_place=place,
            record_types=[RecordType.DEATH],
        )
        return await self.search(query)

    async def search_marriage(
        self,
        surname: str,
        spouse_surname: str | None = None,
        year: int | None = None,
        place: str | None = None,
    ) -> SearchResponse:
        """Search for marriage records."""
        query = SearchQuery(
            surname=surname,
            spouse_name=spouse_surname,
            event_year=year,
            event_place=place,
            record_types=[RecordType.MARRIAGE],
        )
        return await self.search(query)

    def generate_surname_variants(self, surname: str) -> list[str]:
        """
        Generate common spelling variants for a surname.

        Subclasses may override for region-specific variants.
        """
        variants = {surname.lower()}

        # Common substitutions
        substitutions = [
            ("ck", "k"), ("ck", "c"),
            ("x", "cks"), ("x", "ks"),
            ("ae", "a"), ("oe", "o"), ("ue", "u"),
            ("y", "ij"), ("ij", "y"),
            ("dt", "t"), ("dt", "d"),
            ("sch", "sh"), ("sh", "sch"),
            ("ph", "f"), ("f", "ph"),
            ("gh", "g"),
        ]

        base = surname.lower()
        for old, new in substitutions:
            if old in base:
                variants.add(base.replace(old, new))
            if new in base:
                variants.add(base.replace(new, old))

        return sorted(v.title() for v in variants)

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the provider."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection to the provider."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
