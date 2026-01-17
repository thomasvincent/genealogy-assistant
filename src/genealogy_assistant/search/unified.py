"""
Unified search across multiple genealogy providers.

Aggregates results from FamilySearch, Geneanet, Belgian Archives,
FindAGrave, and other providers into a single search interface.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable

from genealogy_assistant.search.base import (
    SearchProvider,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from genealogy_assistant.search.familysearch import FamilySearchProvider, FamilySearchConfig
from genealogy_assistant.search.geneanet import GeneanetProvider, GeneanetConfig
from genealogy_assistant.search.belgian_archives import BelgianArchivesProvider, BelgianArchivesConfig
from genealogy_assistant.search.findagrave import FindAGraveProvider, FindAGraveConfig


@dataclass
class UnifiedSearchConfig:
    """Configuration for unified search."""
    familysearch: FamilySearchConfig | None = None
    geneanet: GeneanetConfig | None = None
    belgian_archives: BelgianArchivesConfig | None = None
    findagrave: FindAGraveConfig | None = None

    # Search behavior
    parallel: bool = True
    timeout_per_provider: float = 30.0
    max_results_per_provider: int = 50


@dataclass
class UnifiedSearchResponse:
    """Combined response from multiple providers."""
    query: SearchQuery
    results: list[SearchResult] = field(default_factory=list)
    responses_by_provider: dict[str, SearchResponse] = field(default_factory=dict)
    total_count: int = 0
    providers_searched: list[str] = field(default_factory=list)
    providers_failed: list[str] = field(default_factory=list)
    search_time_ms: float = 0.0


class UnifiedSearch:
    """
    Unified search across multiple genealogy databases.

    Provides a single interface to search FamilySearch, Geneanet,
    Belgian Archives, and FindAGrave simultaneously.
    """

    def __init__(self, config: UnifiedSearchConfig | None = None):
        """Initialize unified search with configuration."""
        self.config = config or UnifiedSearchConfig()
        self._providers: dict[str, SearchProvider] = {}
        self._connected = False

    async def connect(self) -> None:
        """Initialize and connect all configured providers."""
        # Initialize providers based on config
        if self.config.familysearch:
            self._providers["familysearch"] = FamilySearchProvider(self.config.familysearch)
        else:
            self._providers["familysearch"] = FamilySearchProvider()

        if self.config.geneanet:
            self._providers["geneanet"] = GeneanetProvider(self.config.geneanet)
        else:
            self._providers["geneanet"] = GeneanetProvider()

        if self.config.belgian_archives:
            self._providers["belgian_archives"] = BelgianArchivesProvider(self.config.belgian_archives)
        else:
            self._providers["belgian_archives"] = BelgianArchivesProvider()

        if self.config.findagrave:
            self._providers["findagrave"] = FindAGraveProvider(self.config.findagrave)
        else:
            self._providers["findagrave"] = FindAGraveProvider()

        # Connect all providers
        connect_tasks = [
            provider.connect() for provider in self._providers.values()
        ]
        await asyncio.gather(*connect_tasks, return_exceptions=True)
        self._connected = True

    async def close(self) -> None:
        """Close all provider connections."""
        close_tasks = [
            provider.close() for provider in self._providers.values()
        ]
        await asyncio.gather(*close_tasks, return_exceptions=True)
        self._connected = False

    async def search(
        self,
        query: SearchQuery,
        providers: list[str] | None = None,
    ) -> UnifiedSearchResponse:
        """
        Search across all or specified providers.

        Args:
            query: Search parameters
            providers: List of provider codes to search (None = all)

        Returns:
            UnifiedSearchResponse with aggregated results
        """
        if not self._connected:
            await self.connect()

        import time
        start_time = time.time()

        # Determine which providers to search
        if providers:
            active_providers = {
                k: v for k, v in self._providers.items()
                if k in providers
            }
        else:
            active_providers = self._providers

        # Execute searches
        if self.config.parallel:
            responses = await self._search_parallel(query, active_providers)
        else:
            responses = await self._search_sequential(query, active_providers)

        # Aggregate results
        all_results = []
        providers_searched = []
        providers_failed = []

        for provider_code, response in responses.items():
            if response.error:
                providers_failed.append(provider_code)
            else:
                providers_searched.append(provider_code)
                all_results.extend(response.results)

        # Sort by relevance
        all_results.sort(key=lambda r: r.relevance_score, reverse=True)

        search_time = (time.time() - start_time) * 1000

        return UnifiedSearchResponse(
            query=query,
            results=all_results,
            responses_by_provider=responses,
            total_count=len(all_results),
            providers_searched=providers_searched,
            providers_failed=providers_failed,
            search_time_ms=search_time,
        )

    async def _search_parallel(
        self,
        query: SearchQuery,
        providers: dict[str, SearchProvider],
    ) -> dict[str, SearchResponse]:
        """Execute searches in parallel across providers."""
        async def search_one(code: str, provider: SearchProvider) -> tuple[str, SearchResponse]:
            try:
                response = await asyncio.wait_for(
                    provider.search(query),
                    timeout=self.config.timeout_per_provider,
                )
                return code, response
            except asyncio.TimeoutError:
                return code, SearchResponse(
                    query=query,
                    provider=code,
                    error="Search timed out",
                )
            except Exception as e:
                return code, SearchResponse(
                    query=query,
                    provider=code,
                    error=str(e),
                )

        tasks = [
            search_one(code, provider)
            for code, provider in providers.items()
        ]

        results = await asyncio.gather(*tasks)
        return dict(results)

    async def _search_sequential(
        self,
        query: SearchQuery,
        providers: dict[str, SearchProvider],
    ) -> dict[str, SearchResponse]:
        """Execute searches sequentially across providers."""
        responses = {}

        for code, provider in providers.items():
            try:
                response = await provider.search(query)
                responses[code] = response
            except Exception as e:
                responses[code] = SearchResponse(
                    query=query,
                    provider=code,
                    error=str(e),
                )

        return responses

    async def search_person(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
        providers: list[str] | None = None,
    ) -> UnifiedSearchResponse:
        """Convenience method for person search."""
        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=birth_place,
        )
        return await self.search(query, providers)

    async def search_with_variants(
        self,
        surname: str,
        given_name: str | None = None,
        **kwargs,
    ) -> UnifiedSearchResponse:
        """
        Search with automatic surname variant generation.

        Useful for Belgian/Dutch surnames with spelling variations.
        """
        # Generate variants from first available provider
        if self._providers:
            provider = list(self._providers.values())[0]
            variants = provider.generate_surname_variants(surname)
        else:
            variants = [surname]

        query = SearchQuery(
            surname=surname,
            given_name=given_name,
            surname_variants=variants,
            **kwargs,
        )

        return await self.search(query)

    def get_provider(self, code: str) -> SearchProvider | None:
        """Get a specific provider by code."""
        return self._providers.get(code)

    @property
    def available_providers(self) -> list[str]:
        """List available provider codes."""
        return list(self._providers.keys())

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
