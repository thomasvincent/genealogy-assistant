"""
AI Genealogy Research Assistant

A BCG/GPS-compliant genealogy research tool with Gramps integration.
"""

__version__ = "0.1.0"
__author__ = "Thomas Vincent"

from genealogy_assistant.core.models import (
    Person,
    Family,
    Source,
    Citation,
    ResearchLog,
    ProofSummary,
    ConfidenceLevel,
    EvidenceType,
)
from genealogy_assistant.core.gps import GenealogyProofStandard

__all__ = [
    "Person",
    "Family",
    "Source",
    "Citation",
    "ResearchLog",
    "ProofSummary",
    "ConfidenceLevel",
    "EvidenceType",
    "GenealogyProofStandard",
]
