"""Unified search plugin for Semantic Kernel."""

from __future__ import annotations

from typing import Annotated

from semantic_kernel.functions import kernel_function

from genealogy_assistant.search.unified import UnifiedSearch, UnifiedSearchConfig


class UnifiedSearchPlugin:
    """
    Search across multiple genealogy databases.

    Wraps the existing UnifiedSearch functionality as a Semantic Kernel plugin.
    """

    def __init__(self, providers: list[str] | None = None):
        """
        Initialize the search plugin.

        Args:
            providers: List of search providers to enable
        """
        config = UnifiedSearchConfig()
        if providers:
            config.providers = providers
        self._search = UnifiedSearch(config)
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure search providers are connected."""
        if not self._connected:
            await self._search.connect()
            self._connected = True

    @kernel_function(
        name="search_person",
        description="Search for a person across genealogy databases (FamilySearch, Geneanet, FindAGrave, etc.)",
    )
    async def search_person(
        self,
        surname: Annotated[str, "The surname/family name to search for"],
        given_name: Annotated[str | None, "The given/first name (optional)"] = None,
        birth_year: Annotated[int | None, "Approximate birth year (optional)"] = None,
        birth_place: Annotated[str | None, "Birth place (optional)"] = None,
        death_year: Annotated[int | None, "Approximate death year (optional)"] = None,
        providers: Annotated[list[str] | None, "Specific providers to search"] = None,
    ) -> str:
        """
        Search for a person across genealogy databases.

        Returns formatted search results with source levels.
        """
        await self._ensure_connected()

        response = await self._search.search_person(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=birth_place,
            providers=providers,
        )

        if not response.results:
            return f"No results found for {given_name or ''} {surname}"

        # Format results for LLM consumption
        lines = [f"Found {len(response.results)} results for {given_name or ''} {surname}:\n"]

        for i, result in enumerate(response.results[:20], 1):
            parts = [f"{i}. {result.given_name} {result.surname}"]

            if result.birth_date:
                parts.append(f"b. {result.birth_date.to_gedcom()}")
            if result.death_date:
                parts.append(f"d. {result.death_date.to_gedcom()}")
            if result.birth_place:
                parts.append(f"in {result.birth_place.name}")

            parts.append(f"[{result.provider}]")
            parts.append(f"({result.source_level.value})")

            if result.url:
                parts.append(f"URL: {result.url}")

            lines.append(" ".join(parts))

        return "\n".join(lines)

    @kernel_function(
        name="search_vital_records",
        description="Search specifically for vital records (birth, marriage, death certificates)",
    )
    async def search_vital_records(
        self,
        surname: Annotated[str, "The surname/family name"],
        given_name: Annotated[str, "The given/first name"],
        event_type: Annotated[str, "Type of record: 'birth', 'marriage', or 'death'"],
        year: Annotated[int, "Year of the event"],
        location: Annotated[str, "Location of the event"],
    ) -> str:
        """
        Search for specific vital records.

        Focuses on primary sources (civil registration, parish records).
        """
        await self._ensure_connected()

        # Determine year range based on event type
        if event_type == "birth":
            birth_year = year
            death_year = None
        elif event_type == "death":
            birth_year = None
            death_year = year
        else:
            birth_year = None
            death_year = None

        response = await self._search.search_person(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=location if event_type == "birth" else None,
        )

        # Filter to primary sources only
        primary_results = [
            r for r in response.results
            if r.source_level.value == "primary"
        ]

        if not primary_results:
            return f"No primary source {event_type} records found for {given_name} {surname} in {location} ({year})"

        lines = [f"Found {len(primary_results)} primary source records:\n"]
        for i, result in enumerate(primary_results[:10], 1):
            lines.append(f"{i}. {result.given_name} {result.surname}")
            if result.birth_date:
                lines.append(f"   Date: {result.birth_date.to_gedcom()}")
            if result.birth_place:
                lines.append(f"   Place: {result.birth_place.name}")
            lines.append(f"   Source: {result.provider} ({result.source_level.value})")
            if result.url:
                lines.append(f"   URL: {result.url}")
            lines.append("")

        return "\n".join(lines)

    @kernel_function(
        name="get_available_providers",
        description="Get list of available genealogy search providers",
    )
    def get_available_providers(self) -> str:
        """Get list of available search providers with descriptions."""
        providers = {
            "familysearch": "FamilySearch.org - Free. Billions of records. PRIMARY source for many vital records.",
            "geneanet": "Geneanet.org - European focus, especially French/Belgian. User trees (TERTIARY).",
            "findagrave": "FindAGrave.com - Cemetery records and photos. SECONDARY source.",
            "belgian_archives": "Belgian State Archives - Primary civil registration from 1796.",
            "ancestry": "Ancestry.com - Subscription. Large record collection. Mixed source levels.",
        }

        lines = ["Available genealogy search providers:\n"]
        for provider, desc in providers.items():
            lines.append(f"- {provider}: {desc}")

        return "\n".join(lines)

    async def close(self) -> None:
        """Close search connections."""
        if self._connected:
            await self._search.close()
            self._connected = False
