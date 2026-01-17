"""
Gramps Web API client.

Provides access to Gramps Web instances via REST API.
Reference: https://gramps-project.github.io/gramps-web-api/

Gramps Web API endpoints:
- /api/people - List/search people
- /api/people/{handle} - Get specific person
- /api/families - List/search families
- /api/families/{handle} - Get specific family
- /api/sources - List/search sources
- /api/events - List/search events
- /api/places - List/search places
- /api/media - List/search media objects
- /api/search - Full-text search
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from genealogy_assistant.core.models import (
    Event,
    Family,
    GenealogyDate,
    Name,
    Person,
    Place,
    Source,
    SourceLevel,
)


@dataclass
class GrampsWebConfig:
    """Configuration for Gramps Web connection."""
    base_url: str
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    tree_id: str | None = None  # For multi-tree setups
    timeout: float = 30.0
    verify_ssl: bool = True


class GrampsWebError(Exception):
    """Error from Gramps Web API."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Gramps Web API error {status_code}: {message}")


class GrampsWebClient:
    """
    Client for Gramps Web REST API.

    Provides asynchronous access to Gramps Web instances
    for genealogy research.
    """

    def __init__(self, config: GrampsWebConfig):
        """
        Initialize Gramps Web client.

        Args:
            config: Connection configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._token_expires: datetime | None = None

    async def connect(self) -> None:
        """Establish connection and authenticate."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        )

        # Authenticate if credentials provided
        if self.config.username and self.config.password:
            await self._authenticate()
        elif self.config.api_key:
            self._token = self.config.api_key

    async def _authenticate(self) -> None:
        """Authenticate with username/password."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        response = await self._client.post(
            "/api/token/",
            data={
                "username": self.config.username,
                "password": self.config.password,
            }
        )

        if response.status_code != 200:
            raise GrampsWebError(
                response.status_code,
                f"Authentication failed: {response.text}"
            )

        data = response.json()
        self._token = data.get("access_token")
        # Token expiration handling would go here

    async def close(self) -> None:
        """Close the connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make authenticated GET request."""
        if not self._client:
            raise RuntimeError("Client not connected")

        response = await self._client.get(
            endpoint,
            headers=self._headers(),
            params=params or {}
        )

        if response.status_code == 401:
            # Token expired, re-authenticate
            await self._authenticate()
            response = await self._client.get(
                endpoint,
                headers=self._headers(),
                params=params or {}
            )

        if response.status_code != 200:
            raise GrampsWebError(response.status_code, response.text)

        return response.json()

    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make authenticated POST request."""
        if not self._client:
            raise RuntimeError("Client not connected")

        response = await self._client.post(
            endpoint,
            headers=self._headers(),
            json=data
        )

        if response.status_code not in (200, 201):
            raise GrampsWebError(response.status_code, response.text)

        return response.json()

    # =========================================
    # Person Operations
    # =========================================

    async def get_person(self, handle: str) -> Person | None:
        """Get a person by handle."""
        try:
            data = await self._get(f"/api/people/{handle}")
            return self._person_from_api(data)
        except GrampsWebError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_people(
        self,
        page: int = 1,
        page_size: int = 100,
        sort: str | None = None,
    ) -> list[Person]:
        """List all people with pagination."""
        params = {
            "page": page,
            "pagesize": page_size,
        }
        if sort:
            params["sort"] = sort

        data = await self._get("/api/people/", params=params)

        return [self._person_from_api(p) for p in data]

    async def search_people(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Person]:
        """
        Search for people by name or other attributes.

        Uses Gramps Web full-text search.
        """
        params = {
            "query": query,
            "page": page,
            "pagesize": page_size,
        }

        data = await self._get("/api/search/", params=params)

        # Filter for person results
        people = [
            self._person_from_api(item["object"])
            for item in data
            if item.get("object_type") == "person"
        ]

        return people

    async def find_person_by_name(
        self,
        surname: str | None = None,
        given: str | None = None,
    ) -> list[Person]:
        """Find people by name components."""
        # Build search query
        parts = []
        if surname:
            parts.append(f"surname:{surname}")
        if given:
            parts.append(f"given:{given}")

        if not parts:
            return []

        query = " AND ".join(parts)
        return await self.search_people(query)

    def _person_from_api(self, data: dict) -> Person:
        """Convert API person data to Person model."""
        person = Person(
            gramps_id=data.get("gramps_id"),
        )

        # Handle
        # Note: Gramps Web returns 'handle' field

        # Name
        primary_name = data.get("primary_name", {})
        if primary_name:
            surnames = primary_name.get("surname_list", [])
            surname = surnames[0].get("surname", "") if surnames else ""

            person.names.append(Name(
                given=primary_name.get("first_name", ""),
                surname=surname,
                nickname=primary_name.get("nick", ""),
            ))

        # Sex
        gender = data.get("gender", 2)
        person.sex = {0: "F", 1: "M"}.get(gender, "U")

        # Birth
        birth_ref = data.get("birth_ref_index")
        if birth_ref is not None:
            event_refs = data.get("event_ref_list", [])
            if birth_ref < len(event_refs):
                # Would need to fetch event details
                pass

        # Death
        death_ref = data.get("death_ref_index")
        if death_ref is not None:
            # Would need to fetch event details
            pass

        return person

    async def create_person(self, person: Person) -> str:
        """
        Create a new person in Gramps Web.

        Returns the handle of the created person.
        """
        data = {
            "gramps_id": person.gramps_id,
            "gender": {"M": 1, "F": 0}.get(person.sex, 2),
            "primary_name": {},
            "private": person.is_private,
        }

        if person.primary_name:
            data["primary_name"] = {
                "first_name": person.primary_name.given,
                "surname_list": [{"surname": person.primary_name.surname}],
                "nick": person.primary_name.nickname or "",
            }

        result = await self._post("/api/people/", data)
        return result.get("handle", "")

    # =========================================
    # Family Operations
    # =========================================

    async def get_family(self, handle: str) -> Family | None:
        """Get a family by handle."""
        try:
            data = await self._get(f"/api/families/{handle}")
            return self._family_from_api(data)
        except GrampsWebError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_families(
        self,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Family]:
        """List all families with pagination."""
        params = {
            "page": page,
            "pagesize": page_size,
        }

        data = await self._get("/api/families/", params=params)
        return [self._family_from_api(f) for f in data]

    def _family_from_api(self, data: dict) -> Family:
        """Convert API family data to Family model."""
        return Family(
            gramps_id=data.get("gramps_id"),
            # Would need handle-to-UUID mapping for spouse/child IDs
        )

    # =========================================
    # Source Operations
    # =========================================

    async def get_source(self, handle: str) -> Source | None:
        """Get a source by handle."""
        try:
            data = await self._get(f"/api/sources/{handle}")
            return self._source_from_api(data)
        except GrampsWebError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_sources(
        self,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Source]:
        """List all sources with pagination."""
        params = {
            "page": page,
            "pagesize": page_size,
        }

        data = await self._get("/api/sources/", params=params)
        return [self._source_from_api(s) for s in data]

    async def search_sources(self, query: str) -> list[Source]:
        """Search sources by title or other attributes."""
        params = {"query": f"source:{query}"}
        data = await self._get("/api/search/", params=params)

        sources = [
            self._source_from_api(item["object"])
            for item in data
            if item.get("object_type") == "source"
        ]

        return sources

    def _source_from_api(self, data: dict) -> Source:
        """Convert API source data to Source model."""
        return Source(
            title=data.get("title", ""),
            author=data.get("author", ""),
            publisher=data.get("pubinfo", ""),
            level=SourceLevel.SECONDARY,
            source_type=data.get("type", "unknown"),
        )

    async def create_source(self, source: Source) -> str:
        """Create a new source in Gramps Web."""
        data = {
            "title": source.title,
            "author": source.author or "",
            "pubinfo": source.publisher or "",
        }

        result = await self._post("/api/sources/", data)
        return result.get("handle", "")

    # =========================================
    # Event Operations
    # =========================================

    async def get_event(self, handle: str) -> Event | None:
        """Get an event by handle."""
        try:
            data = await self._get(f"/api/events/{handle}")
            return self._event_from_api(data)
        except GrampsWebError as e:
            if e.status_code == 404:
                return None
            raise

    def _event_from_api(self, data: dict) -> Event:
        """Convert API event data to Event model."""
        event = Event(
            event_type=data.get("type", "Unknown"),
        )

        # Date
        date_data = data.get("date", {})
        if date_data:
            # Parse Gramps date structure
            if date_data.get("dateval"):
                val = date_data["dateval"]
                event.date = GenealogyDate(
                    day=val[0] if len(val) > 0 else None,
                    month=val[1] if len(val) > 1 else None,
                    year=val[2] if len(val) > 2 else None,
                )

        # Place
        place_handle = data.get("place")
        if place_handle:
            # Would need to fetch place details
            pass

        return event

    # =========================================
    # Place Operations
    # =========================================

    async def get_place(self, handle: str) -> Place | None:
        """Get a place by handle."""
        try:
            data = await self._get(f"/api/places/{handle}")
            return self._place_from_api(data)
        except GrampsWebError as e:
            if e.status_code == 404:
                return None
            raise

    async def search_places(self, query: str) -> list[Place]:
        """Search places by name."""
        params = {"query": f"place:{query}"}
        data = await self._get("/api/search/", params=params)

        places = [
            self._place_from_api(item["object"])
            for item in data
            if item.get("object_type") == "place"
        ]

        return places

    def _place_from_api(self, data: dict) -> Place:
        """Convert API place data to Place model."""
        name = data.get("name", {}).get("value", "")
        return Place(
            name=name,
            latitude=data.get("lat"),
            longitude=data.get("long"),
        )

    # =========================================
    # Utility Operations
    # =========================================

    async def get_statistics(self) -> dict[str, int]:
        """Get database statistics from Gramps Web."""
        # Gramps Web may have a stats endpoint
        # If not, we count records
        stats = {}

        try:
            # Try stats endpoint first
            data = await self._get("/api/metadata/")
            if "object_counts" in data:
                return data["object_counts"]
        except GrampsWebError:
            pass

        # Fallback: count via list endpoints
        for obj_type in ["people", "families", "sources", "events", "places"]:
            try:
                data = await self._get(f"/api/{obj_type}/", params={"pagesize": 1})
                # Would need to parse pagination info for total count
                stats[obj_type] = len(data)
            except GrampsWebError:
                stats[obj_type] = 0

        return stats

    async def full_text_search(
        self,
        query: str,
        object_types: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict]:
        """
        Perform full-text search across all object types.

        Returns list of search results with object type and data.
        """
        params = {
            "query": query,
            "page": page,
            "pagesize": page_size,
        }

        data = await self._get("/api/search/", params=params)

        # Filter by object type if specified
        if object_types:
            data = [
                item for item in data
                if item.get("object_type") in object_types
            ]

        return data

    async def export_gedcom(self) -> bytes:
        """
        Export database as GEDCOM.

        Returns GEDCOM file content as bytes.
        """
        response = await self._client.get(
            "/api/exporters/gedcom",
            headers=self._headers(),
        )

        if response.status_code != 200:
            raise GrampsWebError(response.status_code, response.text)

        return response.content

    # =========================================
    # Context Manager
    # =========================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
