"""Gramps Web Adapter.

Provides REST API integration for the Smart Search Router
with Gramps Web installations.
"""

from genealogy_assistant.adapters.gramps_web.api import router as smart_search_router

__all__ = ["smart_search_router"]
