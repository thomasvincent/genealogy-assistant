"""Gramps integration for local and web access."""

from genealogy_assistant.gramps.client import GrampsClient
from genealogy_assistant.gramps.web_api import GrampsWebClient

__all__ = [
    "GrampsClient",
    "GrampsWebClient",
]
