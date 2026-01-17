"""
Belgian State Archives search provider.

Provides access to Belgian civil registration via search.arch.be
Reference: https://search.arch.be/

Coverage:
- 32+ million indexed names from civil status registers
- Births, marriages, deaths from 1796 onward
- Strong coverage for Brabant province including Tervuren
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup
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
class BelgianArchivesConfig:
    """Configuration for Belgian Archives access."""
    base_url: str = "https://search.arch.be"
    api_url: str = "https://search.arch.be/api"
    timeout: float = 30.0
    language: str = "en"  # en, fr, nl, de


class BelgianArchivesProvider(SearchProvider):
    """
    Belgian State Archives search provider.

    Searches the Belgian State Archives person index,
    which covers civil registration from 1796 onward.

    Key collections:
    - Burgerlijke Stand (Civil Registration)
    - Parochieregisters (Parish Registers)
    - Bevolkingsregisters (Population Registers)
    """

    # Belgian province codes
    PROVINCES = {
        "antwerp": "antwerpen",
        "brabant": "brabant",
        "flemish_brabant": "vlaams-brabant",
        "walloon_brabant": "brabant-wallon",
        "brussels": "brussel",
        "east_flanders": "oost-vlaanderen",
        "west_flanders": "west-vlaanderen",
        "hainaut": "henegouwen",
        "liege": "luik",
        "limburg": "limburg",
        "luxembourg": "luxemburg",
        "namur": "namen",
    }

    def __init__(self, config: BelgianArchivesConfig | None = None):
        """Initialize Belgian Archives provider."""
        self.config = config or BelgianArchivesConfig()
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "Belgian State Archives"

    @property
    def code(self) -> str:
        return "belgian_archives"

    @property
    def source_level(self) -> SourceLevel:
        # Archives indexes are secondary; originals are primary
        return SourceLevel.SECONDARY

    async def connect(self) -> None:
        """Establish connection to Belgian Archives."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GenealogyAssistant/1.0)",
                "Accept": "application/json, text/html",
                "Accept-Language": f"{self.config.language},en;q=0.9",
            }
        )

    async def close(self) -> None:
        """Close Belgian Archives connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15)
    )
    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Search Belgian Archives person index.

        Uses the /zoeken-naar-personen (Search for Persons) endpoint.
        """
        start_time = time.time()

        if not self._client:
            return SearchResponse(
                query=query,
                provider=self.code,
                error="Not connected to Belgian Archives",
            )

        params = self._build_query_params(query)

        try:
            # Try API endpoint first
            response = await self._client.get(
                f"/{self.config.language}/zoeken-naar-personen",
                params=params,
            )

            if response.status_code != 200:
                return SearchResponse(
                    query=query,
                    provider=self.code,
                    error=f"Belgian Archives error: {response.status_code}",
                )

            # Parse results
            results = self._parse_results(response.text)
            search_time = (time.time() - start_time) * 1000

            return SearchResponse(
                query=query,
                provider=self.code,
                results=results,
                total_count=len(results),
                page=query.page,
                page_size=query.page_size,
                has_more=len(results) >= query.page_size,
                search_time_ms=search_time,
            )

        except httpx.RequestError as e:
            return SearchResponse(
                query=query,
                provider=self.code,
                error=f"Request error: {str(e)}",
            )

    def _build_query_params(self, query: SearchQuery) -> dict[str, Any]:
        """Build Belgian Archives query parameters."""
        params: dict[str, Any] = {
            "view": "list",
        }

        if query.surname:
            params["search_api_fulltext"] = query.surname
            if query.given_name:
                params["search_api_fulltext"] += f" {query.given_name}"

        if query.birth_year:
            params["year_from"] = query.birth_year - query.birth_year_range
            params["year_to"] = query.birth_year + query.birth_year_range

        if query.birth_place:
            params["place"] = query.birth_place

        # Record type filter
        if RecordType.BIRTH in query.record_types:
            params["type"] = "birth"
        elif RecordType.DEATH in query.record_types:
            params["type"] = "death"
        elif RecordType.MARRIAGE in query.record_types:
            params["type"] = "marriage"

        # Pagination
        params["page"] = query.page - 1  # Zero-indexed

        return params

    def _parse_results(self, html: str) -> list[SearchResult]:
        """Parse Belgian Archives search results."""
        results = []
        soup = BeautifulSoup(html, "lxml")

        # Find result table or list
        result_rows = soup.find_all("tr", class_="search-result")

        for row in result_rows:
            result = self._parse_result_row(row)
            if result:
                results.append(result)

        return results

    def _parse_result_row(self, row: Any) -> SearchResult | None:
        """Parse a single result row."""
        cells = row.find_all("td")
        if len(cells) < 3:
            return None

        # Extract name
        name_cell = cells[0]
        name_link = name_cell.find("a")
        if not name_link:
            return None

        full_name = name_link.get_text(strip=True)

        # Parse name
        parts = full_name.split(",")
        surname = parts[0].strip() if parts else ""
        given_name = parts[1].strip() if len(parts) > 1 else ""

        result = SearchResult(
            provider=self.code,
            given_name=given_name,
            surname=surname,
            source_level=SourceLevel.SECONDARY,
        )

        # Extract date
        if len(cells) > 1:
            date_text = cells[1].get_text(strip=True)
            if date_text:
                # Parse year
                import re
                year_match = re.search(r"\d{4}", date_text)
                if year_match:
                    result.birth_date = GenealogyDate(year=int(year_match.group()))

        # Extract place
        if len(cells) > 2:
            place_text = cells[2].get_text(strip=True)
            if place_text:
                result.birth_place = Place(name=place_text)

        # Extract link
        href = name_link.get("href", "")
        if href:
            result.record_url = f"{self.config.base_url}{href}"
            # Extract record ID
            import re
            id_match = re.search(r"/(\d+)$", href)
            if id_match:
                result.record_id = id_match.group(1)

        return result

    async def get_record(self, record_id: str) -> SearchResult | None:
        """Get a specific record from Belgian Archives."""
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"/{self.config.language}/zoeken-naar-personen/{record_id}"
            )

            if response.status_code != 200:
                return None

            return self._parse_record_page(response.text, record_id)

        except httpx.RequestError:
            return None

    def _parse_record_page(self, html: str, record_id: str) -> SearchResult | None:
        """Parse a Belgian Archives record detail page."""
        soup = BeautifulSoup(html, "lxml")

        # Find person details
        name_elem = soup.find("h1", class_="page-title")
        if not name_elem:
            return None

        full_name = name_elem.get_text(strip=True)
        parts = full_name.split(",")
        surname = parts[0].strip() if parts else ""
        given_name = parts[1].strip() if len(parts) > 1 else ""

        result = SearchResult(
            provider=self.code,
            record_id=record_id,
            given_name=given_name,
            surname=surname,
            source_level=SourceLevel.SECONDARY,
            record_url=f"{self.config.base_url}/{self.config.language}/zoeken-naar-personen/{record_id}",
        )

        # Extract additional details from the page
        details = soup.find("div", class_="record-details")
        if details:
            # Parse structured data
            for row in details.find_all("tr"):
                label = row.find("th")
                value = row.find("td")
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)

                    if "birth" in label_text or "geboorte" in label_text:
                        result.birth_date = GenealogyDate.from_string(value_text)
                    elif "death" in label_text or "overlijden" in label_text:
                        result.death_date = GenealogyDate.from_string(value_text)
                    elif "place" in label_text or "plaats" in label_text:
                        result.birth_place = Place(name=value_text)
                    elif "father" in label_text or "vader" in label_text:
                        result.father_name = value_text
                    elif "mother" in label_text or "moeder" in label_text:
                        result.mother_name = value_text

        return result

    async def search_commune(
        self,
        commune: str,
        surname: str | None = None,
        record_type: RecordType | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SearchResponse:
        """
        Search records for a specific Belgian commune.

        Communes like Tervuren, Overijse, Uccle, etc.
        """
        query = SearchQuery(
            surname=surname,
            birth_place=commune,
            birth_year=(year_from + year_to) // 2 if year_from and year_to else None,
            birth_year_range=((year_to - year_from) // 2) if year_from and year_to else 5,
            region=Region.BELGIUM,
            record_types=[record_type] if record_type else [],
        )
        return await self.search(query)

    def generate_surname_variants(self, surname: str) -> list[str]:
        """Generate Belgian surname variants."""
        variants = set()
        base = surname.lower()
        variants.add(base)

        # Belgian/Dutch specific patterns
        patterns = [
            # ck/k/c variations
            ("ck", "k"), ("ck", "c"), ("k", "ck"),
            # x/cks/ks variations
            ("x", "cks"), ("x", "ks"), ("cks", "x"), ("ks", "x"),
            # ae/a, oe/o, ue/u variations
            ("ae", "a"), ("oe", "o"), ("ue", "u"),
            ("a", "ae"), ("o", "oe"), ("u", "ue"),
            # y/ij/i variations (common in Dutch)
            ("y", "ij"), ("ij", "y"), ("ij", "i"), ("i", "ij"),
            # dt/t/d endings
            ("dt", "t"), ("dt", "d"), ("t", "dt"),
            # sch/sh
            ("sch", "sh"), ("sh", "sch"),
            # Double consonants
            ("ss", "s"), ("s", "ss"),
            ("tt", "t"), ("t", "tt"),
            ("nn", "n"), ("n", "nn"),
            ("ll", "l"), ("l", "ll"),
        ]

        for old, new in patterns:
            if old in base:
                variants.add(base.replace(old, new))

        # Van/de prefixes
        if base.startswith("van "):
            variants.add(base.replace("van ", ""))
            variants.add(base.replace("van ", "vander"))
        if base.startswith("de "):
            variants.add(base.replace("de ", ""))

        return sorted(v.title() for v in variants)
