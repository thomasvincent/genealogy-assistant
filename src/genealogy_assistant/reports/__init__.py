"""
GPS-compliant genealogy report generation.

Generates professional research reports following BCG standards.
"""

from genealogy_assistant.reports.proof import ProofSummaryReport
from genealogy_assistant.reports.research_log import ResearchLogReport
from genealogy_assistant.reports.family_group import FamilyGroupSheet
from genealogy_assistant.reports.pedigree import PedigreeChart
from genealogy_assistant.reports.citations import CitationFormatter

__all__ = [
    "ProofSummaryReport",
    "ResearchLogReport",
    "FamilyGroupSheet",
    "PedigreeChart",
    "CitationFormatter",
]
