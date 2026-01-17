"""
FamilySearch search provider.

Provides access to FamilySearch historical records and family trees.
Reference: https://www.familysearch.org/developers/

Note: FamilySearch API requires registration and authentication.
This implementation provides the structure; actual API access
requires valid credentials.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from genealogy_assistant.core.models import GenealogyDate, Place, SourceLevel
from genealogy_assistant.search.base import (
    RecordType,
    Region,
    SearchProvider,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


@dataclass
class FamilySearchConfig:
    """Configuration for FamilySearch API access."""
    api_key: str | None = None
    session_id: str | None = None
    base_url: str = "https://api.familysearch.org"
    timeout: float = 30.0


class FamilySearchProvider(SearchProvider):
    """
    FamilySearch search provider.

    Searches FamilySearch historical records and indexes.
    Supports civil registration, census, church records, etc.

    Belgian collections of note:
    - Belgium, Brabant, Civil Registration, 1796-1910
    - Belgium, Church Records, 1574-1970
    - Belgium Population Registers, 1846-1920
    """

    # Belgian collection IDs
    BELGIAN_COLLECTIONS = {
        "brabant_civil": "2037955",
        "church_records": "1542666",
        "population_registers": "1876800",
    }

    def __init__(self, config: FamilySearchConfig | None = None):
        """Initialize FamilySearch provider."""
        self.config = config or FamilySearchConfig()
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "FamilySearch"

    @property
    def code(self) -> str:
        return "familysearch"

    @property
    def source_level(self) -> SourceLevel:
        # FamilySearch indexes are secondary; images are primary
        return SourceLevel.SECONDARY

    async def connect(self) -> None:
        """Establish connection to FamilySearch."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "GenealogyAssistant/1.0",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=self.config.timeout,
        )

    async def close(self) -> None:
        """Close FamilySearch connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Search FamilySearch historical records.

        Uses the /platform/search/records endpoint.
        """
        start_time = time.time()

        if not self._client:
            return SearchResponse(
                query=query,
                provider=self.code,
                error="Not connected to FamilySearch",
            )

        # Build query parameters
        params = self._build_query_params(query)

        try:
            response = await self._client.get(
                "/platform/search/records",
                params=params,
            )

            if response.status_code == 401:
                return SearchResponse(
                    query=query,
                    provider=self.code,
                    error="Authentication required for FamilySearch API",
                )

            if response.status_code != 200:
                return SearchResponse(
                    query=query,
                    provider=self.code,
                    error=f"FamilySearch API error: {response.status_code}",
                )

            data = response.json()
            results = self._parse_results(data)

            search_time = (time.time() - start_time) * 1000

            return SearchResponse(
                query=query,
                provider=self.code,
                results=results,
                total_count=data.get("count", len(results)),
                page=query.page,
                page_size=query.page_size,
                has_more=data.get("count", 0) > query.page * query.page_size,
                search_time_ms=search_time,
            )

        except httpx.RequestError as e:
            return SearchResponse(
                query=query,
                provider=self.code,
                error=f"Request error: {str(e)}",
            )

    def _build_query_params(self, query: SearchQuery) -> dict[str, Any]:
        """Build FamilySearch query parameters."""
        params: dict[str, Any] = {
            "count": query.page_size,
            "offset": (query.page - 1) * query.page_size,
        }

        # Name parameters
        if query.surname:
            params["surname"] = query.surname
            # Add exact match option
            if not query.surname_variants:
                params["surname.exact"] = "true"

        if query.given_name:
            params["givenName"] = query.given_name

        # Date parameters
        if query.birth_year:
            params["birthLikeDate"] = f"{query.birth_year}~"
            params["birthLikeDate.from"] = query.birth_year - query.birth_year_range
            params["birthLikeDate.to"] = query.birth_year + query.birth_year_range

        if query.death_year:
            params["deathLikeDate"] = f"{query.death_year}~"

        # Place parameters
        if query.birth_place:
            params["birthLikePlace"] = query.birth_place

        if query.death_place:
            params["deathLikePlace"] = query.death_place

        # Family parameters
        if query.father_name:
            params["fatherSurname"] = query.father_name
        if query.mother_name:
            params["motherSurname"] = query.mother_name
        if query.spouse_name:
            params["spouseSurname"] = query.spouse_name

        # Collection filter for Belgian records
        if query.region == Region.BELGIUM:
            # Filter to Belgian collections
            params["collectionId"] = list(self.BELGIAN_COLLECTIONS.values())

        return params

    def _parse_results(self, data: dict) -> list[SearchResult]:
        """Parse FamilySearch search results."""
        results = []

        entries = data.get("entries", [])
        for entry in entries:
            content = entry.get("content", {})
            gedcomx = content.get("gedcomx", {})

            # Get person data
            persons = gedcomx.get("persons", [])
            if not persons:
                continue

            person = persons[0]
            result = self._parse_person(person, entry)
            if result:
                results.append(result)

        return results

    def _parse_person(self, person: dict, entry: dict) -> SearchResult | None:
        """Parse a single person from FamilySearch results."""
        # Names
        names = person.get("names", [])
        given_name = ""
        surname = ""

        if names:
            name_forms = names[0].get("nameForms", [])
            if name_forms:
                parts = name_forms[0].get("parts", [])
                for part in parts:
                    if part.get("type") == "http://gedcomx.org/Given":
                        given_name = part.get("value", "")
                    elif part.get("type") == "http://gedcomx.org/Surname":
                        surname = part.get("value", "")

        if not given_name and not surname:
            return None

        result = SearchResult(
            provider=self.code,
            record_id=person.get("id", ""),
            given_name=given_name,
            surname=surname,
            source_level=SourceLevel.SECONDARY,
        )

        # Gender
        gender = person.get("gender", {})
        if gender.get("type") == "http://gedcomx.org/Male":
            result.sex = "M"
        elif gender.get("type") == "http://gedcomx.org/Female":
            result.sex = "F"

        # Facts (birth, death, etc.)
        facts = person.get("facts", [])
        for fact in facts:
            fact_type = fact.get("type", "")
            fact_date = fact.get("date", {})
            fact_place = fact.get("place", {})

            parsed_date = self._parse_date(fact_date)
            parsed_place = self._parse_place(fact_place)

            if "Birth" in fact_type:
                result.birth_date = parsed_date
                result.birth_place = parsed_place
            elif "Death" in fact_type:
                result.death_date = parsed_date
                result.death_place = parsed_place

        # Links
        links = entry.get("links", {})
        record_link = links.get("record", {})
        if record_link:
            result.record_url = record_link.get("href")

        # Collection info
        result.collection_name = entry.get("title", "")

        # Score
        result.relevance_score = entry.get("score", 0.0)

        # Raw data for debugging
        result.raw_data = person

        return result

    def _parse_date(self, date_data: dict) -> GenealogyDate | None:
        """Parse FamilySearch date."""
        if not date_data:
            return None

        original = date_data.get("original", "")
        if not original:
            return None

        # Try to parse the formal date if available
        formal = date_data.get("formal", "")
        if formal:
            # FamilySearch formal dates are like "+1862-02-07"
            try:
                parts = formal.lstrip("+").split("-")
                return GenealogyDate(
                    year=int(parts[0]) if len(parts) > 0 else None,
                    month=int(parts[1]) if len(parts) > 1 else None,
                    day=int(parts[2]) if len(parts) > 2 else None,
                    original_text=original,
                )
            except (ValueError, IndexError):
                pass

        # Fall back to original text
        return GenealogyDate.from_string(original)

    def _parse_place(self, place_data: dict) -> Place | None:
        """Parse FamilySearch place."""
        if not place_data:
            return None

        original = place_data.get("original", "")
        if not original:
            return None

        return Place.from_string(original)

    async def get_record(self, record_id: str) -> SearchResult | None:
        """Get a specific record by ID."""
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"/platform/records/personas/{record_id}"
            )

            if response.status_code != 200:
                return None

            data = response.json()
            persons = data.get("persons", [])

            if not persons:
                return None

            return self._parse_person(persons[0], {"links": data.get("links", {})})

        except httpx.RequestError:
            return None

    async def get_collection_info(self, collection_id: str) -> dict | None:
        """Get information about a FamilySearch collection."""
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"/platform/collections/{collection_id}"
            )

            if response.status_code != 200:
                return None

            return response.json()

        except httpx.RequestError:
            return None

    async def search_belgian_civil(
        self,
        surname: str,
        given_name: str | None = None,
        year: int | None = None,
        commune: str | None = None,
    ) -> SearchResponse:
        """
        Search Belgian Brabant civil registration.

        Convenience method for searching Belgian records.
        """
        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            birth_year=year,
            birth_place=commune,
            region=Region.BELGIUM,
            options={"collection": "brabant_civil"},
        )
        return await self.search(query)

    def generate_surname_variants(self, surname: str) -> list[str]:
        """Generate Belgian/Dutch surname variants."""
        variants = super().generate_surname_variants(surname)

        # Additional Belgian/Dutch specific variants
        base = surname.lower()

        # Van/Van der variations
        if base.startswith("van "):
            variants.add(base.replace("van ", "van"))
            variants.add(base.replace("van ", "vander"))
        if base.startswith("vander"):
            variants.add(base.replace("vander", "van der "))
            variants.add(base.replace("vander", "van "))

        # De/d' variations
        if base.startswith("de "):
            variants.add(base.replace("de ", "d'"))
            variants.add(base.replace("de ", "de"))
        if base.startswith("d'"):
            variants.add(base.replace("d'", "de "))

        return sorted(v.title() for v in variants)
