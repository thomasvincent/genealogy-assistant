"""
Geneanet search provider.

Provides access to Geneanet genealogy database and user trees.
Reference: https://www.geneanet.org/

Note: Geneanet has limited API access. This implementation
uses web scraping for search functionality.
"""

from __future__ import annotations

import re
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
class GeneanetConfig:
    """Configuration for Geneanet access."""
    username: str | None = None
    password: str | None = None
    base_url: str = "https://www.geneanet.org"
    timeout: float = 30.0


class GeneanetProvider(SearchProvider):
    """
    Geneanet search provider.

    Searches Geneanet's extensive European genealogy database,
    particularly strong for French and Belgian records.

    Features:
    - User-submitted family trees
    - Civil registration indexes
    - Parish register indexes
    - Military records
    """

    def __init__(self, config: GeneanetConfig | None = None):
        """Initialize Geneanet provider."""
        self.config = config or GeneanetConfig()
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False

    @property
    def name(self) -> str:
        return "Geneanet"

    @property
    def code(self) -> str:
        return "geneanet"

    @property
    def source_level(self) -> SourceLevel:
        # Geneanet trees are tertiary; need corroboration
        return SourceLevel.TERTIARY

    async def connect(self) -> None:
        """Establish connection to Geneanet."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GenealogyAssistant/1.0)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,nl;q=0.7",
            }
        )

        # Authenticate if credentials provided
        if self.config.username and self.config.password:
            await self._authenticate()

    async def _authenticate(self) -> None:
        """Authenticate with Geneanet."""
        if not self._client:
            return

        # Get login page for CSRF token
        login_page = await self._client.get("/connexion/")

        # Extract CSRF token from form
        soup = BeautifulSoup(login_page.text, "lxml")
        csrf_input = soup.find("input", {"name": "_csrf_token"})
        csrf_token = csrf_input.get("value") if csrf_input else ""

        # Submit login
        response = await self._client.post(
            "/connexion/",
            data={
                "_username": self.config.username,
                "_password": self.config.password,
                "_csrf_token": csrf_token,
            }
        )

        self._authenticated = response.status_code == 200

    async def close(self) -> None:
        """Close Geneanet connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15)
    )
    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Search Geneanet family trees.

        Uses the /fonds/individus search endpoint.
        """
        start_time = time.time()

        if not self._client:
            return SearchResponse(
                query=query,
                provider=self.code,
                error="Not connected to Geneanet",
            )

        # Build search URL
        params = self._build_query_params(query)

        try:
            response = await self._client.get(
                "/fonds/individus/",
                params=params,
            )

            if response.status_code != 200:
                return SearchResponse(
                    query=query,
                    provider=self.code,
                    error=f"Geneanet search error: {response.status_code}",
                )

            # Parse HTML results
            results = self._parse_search_page(response.text)
            search_time = (time.time() - start_time) * 1000

            return SearchResponse(
                query=query,
                provider=self.code,
                results=results,
                total_count=len(results),  # Would need to parse pagination
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
        """Build Geneanet query parameters."""
        params: dict[str, Any] = {}

        if query.surname:
            params["nom"] = query.surname

        if query.given_name:
            params["prenom"] = query.given_name

        if query.birth_year:
            params["annee_naissance"] = query.birth_year
            params["annee_naissance_delta"] = query.birth_year_range

        if query.death_year:
            params["annee_deces"] = query.death_year

        if query.birth_place:
            params["lieu_naissance"] = query.birth_place

        # Region filter
        if query.region == Region.BELGIUM:
            params["pays"] = "BEL"
        elif query.region == Region.NETHERLANDS:
            params["pays"] = "NLD"
        elif query.region == Region.FRANCE:
            params["pays"] = "FRA"

        # Pagination
        params["page"] = query.page
        params["size"] = query.page_size

        return params

    def _parse_search_page(self, html: str) -> list[SearchResult]:
        """Parse Geneanet search results HTML."""
        results = []
        soup = BeautifulSoup(html, "lxml")

        # Find result items
        result_items = soup.find_all("div", class_="search-result-item")

        for item in result_items:
            result = self._parse_result_item(item)
            if result:
                results.append(result)

        return results

    def _parse_result_item(self, item: Any) -> SearchResult | None:
        """Parse a single Geneanet search result item."""
        # Extract name
        name_elem = item.find("a", class_="name")
        if not name_elem:
            return None

        full_name = name_elem.get_text(strip=True)

        # Parse name into given/surname
        # Geneanet format is typically "SURNAME Given Name"
        parts = full_name.split()
        surname = ""
        given_name = ""

        for i, part in enumerate(parts):
            if part.isupper():
                surname += part + " "
            else:
                given_name = " ".join(parts[i:])
                break

        surname = surname.strip()
        given_name = given_name.strip()

        result = SearchResult(
            provider=self.code,
            given_name=given_name,
            surname=surname,
            source_level=SourceLevel.TERTIARY,
        )

        # Extract dates
        dates_elem = item.find("span", class_="dates")
        if dates_elem:
            dates_text = dates_elem.get_text(strip=True)
            birth_match = re.search(r"[°*]\s*(\d{4})", dates_text)
            death_match = re.search(r"[†+]\s*(\d{4})", dates_text)

            if birth_match:
                result.birth_date = GenealogyDate(year=int(birth_match.group(1)))
            if death_match:
                result.death_date = GenealogyDate(year=int(death_match.group(1)))

        # Extract place
        place_elem = item.find("span", class_="place")
        if place_elem:
            place_text = place_elem.get_text(strip=True)
            result.birth_place = Place(name=place_text)

        # Extract tree owner/link
        link = name_elem.get("href", "")
        if link:
            result.record_url = f"{self.config.base_url}{link}"

            # Extract record ID from URL
            match = re.search(r"/(\w+)\?", link)
            if match:
                result.record_id = match.group(1)

        # Extract tree owner
        owner_elem = item.find("span", class_="owner")
        if owner_elem:
            result.collection_name = f"Tree by {owner_elem.get_text(strip=True)}"

        return result

    async def get_record(self, record_id: str) -> SearchResult | None:
        """Get a specific person's page from Geneanet."""
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/{record_id}")

            if response.status_code != 200:
                return None

            return self._parse_person_page(response.text, record_id)

        except httpx.RequestError:
            return None

    def _parse_person_page(self, html: str, record_id: str) -> SearchResult | None:
        """Parse a Geneanet person page."""
        soup = BeautifulSoup(html, "lxml")

        # Find person name
        name_elem = soup.find("h1", id="person-title")
        if not name_elem:
            return None

        full_name = name_elem.get_text(strip=True)

        # Parse name (similar to search results)
        parts = full_name.split()
        surname = ""
        given_name = ""

        for i, part in enumerate(parts):
            if part.isupper():
                surname += part + " "
            else:
                given_name = " ".join(parts[i:])
                break

        result = SearchResult(
            provider=self.code,
            record_id=record_id,
            given_name=given_name.strip(),
            surname=surname.strip(),
            source_level=SourceLevel.TERTIARY,
            record_url=f"{self.config.base_url}/{record_id}",
        )

        # Parse additional details from page
        # This would need more detailed parsing of the person page structure

        return result

    async def get_user_tree_info(self, username: str) -> dict | None:
        """Get information about a Geneanet user's tree."""
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/{username}")

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "lxml")

            # Extract tree statistics
            stats = {}
            stats_elem = soup.find("div", class_="tree-stats")
            if stats_elem:
                person_count = stats_elem.find("span", class_="person-count")
                if person_count:
                    stats["person_count"] = int(
                        re.sub(r"\D", "", person_count.get_text())
                    )

            return stats

        except (httpx.RequestError, ValueError):
            return None

    async def search_by_tree_owner(
        self,
        owner_username: str,
        surname: str | None = None,
    ) -> SearchResponse:
        """
        Search within a specific user's tree.

        Useful when you've identified a potential relative's tree.
        """
        if not self._client:
            return SearchResponse(
                query=SearchQuery(),
                provider=self.code,
                error="Not connected",
            )

        params = {"tree": owner_username}
        if surname:
            params["nom"] = surname

        try:
            response = await self._client.get(
                f"/gw/{owner_username}",
                params=params,
            )

            if response.status_code != 200:
                return SearchResponse(
                    query=SearchQuery(surname=surname),
                    provider=self.code,
                    error=f"Error: {response.status_code}",
                )

            results = self._parse_search_page(response.text)

            return SearchResponse(
                query=SearchQuery(surname=surname),
                provider=self.code,
                results=results,
                total_count=len(results),
            )

        except httpx.RequestError as e:
            return SearchResponse(
                query=SearchQuery(surname=surname),
                provider=self.code,
                error=str(e),
            )
