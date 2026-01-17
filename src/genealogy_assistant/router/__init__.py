"""Smart Search Router for genealogical databases.

Routes searches to appropriate databases based on person context
(location, time period, ethnicity).
"""

from genealogy_assistant.router.registry import SourceRegistry
from genealogy_assistant.router.smart_router import SmartRouter, SourceRecommendation

__all__ = ["SourceRegistry", "SmartRouter", "SourceRecommendation"]
