"""
Genealogy database search integrations.

Provides unified search across multiple genealogy databases:
- FamilySearch
- Geneanet
- Belgian State Archives
- FindAGrave
- Ancestry (future)
"""

from genealogy_assistant.search.base import (
    SearchProvider,
    SearchResult,
    SearchQuery,
    RecordType,
)
from genealogy_assistant.search.familysearch import FamilySearchProvider
from genealogy_assistant.search.geneanet import GeneanetProvider
from genealogy_assistant.search.belgian_archives import BelgianArchivesProvider
from genealogy_assistant.search.findagrave import FindAGraveProvider
from genealogy_assistant.search.unified import UnifiedSearch

__all__ = [
    "SearchProvider",
    "SearchResult",
    "SearchQuery",
    "RecordType",
    "FamilySearchProvider",
    "GeneanetProvider",
    "BelgianArchivesProvider",
    "FindAGraveProvider",
    "UnifiedSearch",
]
