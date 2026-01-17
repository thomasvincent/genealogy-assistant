"""
FindAGrave search provider.

Provides access to FindAGrave cemetery records.
Reference: https://www.findagrave.com/
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from genealogy_assistant.core.models import GenealogyDate, Place, SourceLevel
from genealogy_assistant.search.base import (
    RecordType,
    SearchProvider,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


@dataclass
class FindAGraveConfig:
    """Configuration for FindAGrave access."""
    base_url: str = "https://www.findagrave.com"
    timeout: float = 30.0


class FindAGraveProvider(SearchProvider):
    """FindAGrave cemetery records search provider."""

    def __init__(self, config: FindAGraveConfig | None = None):
        self.config = config or FindAGraveConfig()
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "FindAGrave"

    @property
    def code(self) -> str:
        return "findagrave"

    @property
    def source_level(self) -> SourceLevel:
        return SourceLevel.SECONDARY

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GenealogyAssistant/1.0)"},
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, query: SearchQuery) -> SearchResponse:
        """Search FindAGrave memorial records."""
        start_time = time.time()

        if not self._client:
            return SearchResponse(query=query, provider=self.code, error="Not connected")

        params = {
            "firstname": query.given_name or "",
            "lastname": query.surname or "",
            "page": query.page,
        }

        if query.birth_year:
            params["birthyear"] = query.birth_year
        if query.death_year:
            params["deathyear"] = query.death_year
        if query.death_place:
            params["location"] = query.death_place

        try:
            response = await self._client.get("/memorial/search", params=params)

            if response.status_code != 200:
                return SearchResponse(
                    query=query, provider=self.code,
                    error=f"FindAGrave error: {response.status_code}"
                )

            results = self._parse_results(response.text)
            search_time = (time.time() - start_time) * 1000

            return SearchResponse(
                query=query, provider=self.code,
                results=results, total_count=len(results),
                page=query.page, page_size=query.page_size,
                has_more=len(results) >= 20,
                search_time_ms=search_time,
            )

        except httpx.RequestError as e:
            return SearchResponse(query=query, provider=self.code, error=str(e))

    def _parse_results(self, html: str) -> list[SearchResult]:
        results = []
        soup = BeautifulSoup(html, "lxml")

        for item in soup.find_all("div", class_="memorial-item"):
            name_elem = item.find("a", class_="memorial-name")
            if not name_elem:
                continue

            full_name = name_elem.get_text(strip=True)
            parts = full_name.rsplit(" ", 1)
            given = parts[0] if parts else ""
            surname = parts[1] if len(parts) > 1 else ""

            result = SearchResult(
                provider=self.code,
                given_name=given,
                surname=surname,
                source_level=SourceLevel.SECONDARY,
                event_type=RecordType.BURIAL,
            )

            href = name_elem.get("href", "")
            if href:
                result.record_url = f"{self.config.base_url}{href}"
                match = re.search(r"/memorial/(\d+)/", href)
                if match:
                    result.record_id = match.group(1)

            dates_elem = item.find("span", class_="dates")
            if dates_elem:
                dates_text = dates_elem.get_text(strip=True)
                birth_match = re.search(r"(\d{4})\s*[-–]", dates_text)
                death_match = re.search(r"[-–]\s*(\d{4})", dates_text)
                if birth_match:
                    result.birth_date = GenealogyDate(year=int(birth_match.group(1)))
                if death_match:
                    result.death_date = GenealogyDate(year=int(death_match.group(1)))

            cemetery_elem = item.find("span", class_="cemetery-name")
            if cemetery_elem:
                result.event_place = Place(name=cemetery_elem.get_text(strip=True))

            results.append(result)

        return results

    async def get_record(self, record_id: str) -> SearchResult | None:
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/memorial/{record_id}")
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "lxml")
            name_elem = soup.find("h1", id="bio-name")
            if not name_elem:
                return None

            full_name = name_elem.get_text(strip=True)
            parts = full_name.rsplit(" ", 1)

            return SearchResult(
                provider=self.code,
                record_id=record_id,
                given_name=parts[0] if parts else "",
                surname=parts[1] if len(parts) > 1 else "",
                source_level=SourceLevel.SECONDARY,
                record_url=f"{self.config.base_url}/memorial/{record_id}",
                event_type=RecordType.BURIAL,
            )

        except httpx.RequestError:
            return None
