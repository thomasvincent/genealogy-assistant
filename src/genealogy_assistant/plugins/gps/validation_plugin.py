"""GPS validation plugin for Semantic Kernel."""

from __future__ import annotations

from typing import Annotated

from semantic_kernel.functions import kernel_function

from genealogy_assistant.core.gps import GenealogyProofStandard
from genealogy_assistant.core.models import ConfidenceLevel, ProofSummary


class GPSValidationPlugin:
    """
    Genealogical Proof Standard validation plugin.

    Wraps GenealogyProofStandard for validating research against GPS requirements.
    """

    def __init__(self):
        """Initialize the GPS plugin."""
        self._gps = GenealogyProofStandard()

    @kernel_function(
        name="validate_proof",
        description="Validate a proof summary against GPS (Genealogical Proof Standard) requirements",
    )
    def validate_proof(
        self,
        conclusion: Annotated[str, "The genealogical conclusion being validated"],
        evidence_count: Annotated[int, "Number of pieces of evidence"],
        has_primary_sources: Annotated[bool, "Whether primary sources are included"],
        has_conflicts: Annotated[bool, "Whether there are conflicting pieces of evidence"],
        conflicts_resolved: Annotated[bool, "Whether all conflicts have been resolved"],
        exhaustive_search: Annotated[bool, "Whether an exhaustive search was conducted"],
    ) -> str:
        """
        Validate a proof summary against GPS requirements.

        GPS requires:
        1. Reasonably exhaustive research
        2. Complete and accurate source citations
        3. Analysis and correlation of evidence
        4. Resolution of conflicting evidence
        5. Written conclusion
        """
        issues = []
        passed = []

        # Check exhaustive research
        if exhaustive_search:
            passed.append("1. Reasonably exhaustive research: PASS")
        else:
            issues.append("1. Reasonably exhaustive research: FAIL - Search not marked as exhaustive")

        # Check source citations
        if evidence_count > 0 and has_primary_sources:
            passed.append("2. Complete source citations with primary sources: PASS")
        elif evidence_count > 0:
            issues.append("2. Source citations: PARTIAL - No primary sources included")
        else:
            issues.append("2. Source citations: FAIL - No evidence cited")

        # Check evidence analysis
        if evidence_count >= 2:
            passed.append("3. Analysis and correlation of evidence: PASS")
        else:
            issues.append("3. Evidence analysis: FAIL - Need multiple pieces of evidence to correlate")

        # Check conflict resolution
        if not has_conflicts:
            passed.append("4. Conflict resolution: PASS - No conflicts to resolve")
        elif conflicts_resolved:
            passed.append("4. Conflict resolution: PASS - All conflicts resolved")
        else:
            issues.append("4. Conflict resolution: FAIL - Unresolved conflicts remain")

        # Check written conclusion
        if conclusion:
            passed.append("5. Written conclusion: PASS")
        else:
            issues.append("5. Written conclusion: FAIL - No conclusion provided")

        # Determine overall result
        is_gps_compliant = len(issues) == 0

        lines = ["GPS Compliance Check:\n"]
        lines.extend(passed)
        if issues:
            lines.append("\nISSUES:")
            lines.extend(issues)

        lines.append(f"\nOVERALL: {'GPS COMPLIANT' if is_gps_compliant else 'NOT GPS COMPLIANT'}")

        return "\n".join(lines)

    @kernel_function(
        name="assess_confidence",
        description="Assess the confidence level for a genealogical conclusion (1-5 scale)",
    )
    def assess_confidence(
        self,
        primary_source_count: Annotated[int, "Number of primary sources"],
        secondary_source_count: Annotated[int, "Number of secondary sources"],
        tertiary_source_count: Annotated[int, "Number of tertiary sources"],
        has_direct_evidence: Annotated[bool, "Whether direct evidence exists"],
        has_conflicts: Annotated[bool, "Whether there are unresolved conflicts"],
        exhaustive_search: Annotated[bool, "Whether search was exhaustive"],
    ) -> str:
        """
        Assess the confidence level for a genealogical conclusion.

        Returns confidence level from 1 (Speculative) to 5 (GPS Complete).
        """
        case = {
            "primary_count": primary_source_count,
            "secondary_count": secondary_source_count,
            "tertiary_count": tertiary_source_count,
            "has_direct_evidence": has_direct_evidence,
            "has_conflicts": has_conflicts,
            "exhaustive_search": exhaustive_search,
        }

        level = self._gps.assess_confidence(case)

        descriptions = {
            ConfidenceLevel.GPS_COMPLETE: "5 - GPS Complete: Meets all GPS requirements with exhaustive research",
            ConfidenceLevel.STRONG: "4 - Strong: Well-supported by multiple primary sources",
            ConfidenceLevel.REASONABLE: "3 - Reasonable: Supported by evidence but room for improvement",
            ConfidenceLevel.WEAK: "2 - Weak: Limited evidence, needs more research",
            ConfidenceLevel.SPECULATIVE: "1 - Speculative: Hypothesis only, little supporting evidence",
        }

        lines = [
            f"Confidence Assessment: {descriptions[level]}",
            "",
            "Evidence Summary:",
            f"  Primary sources: {primary_source_count}",
            f"  Secondary sources: {secondary_source_count}",
            f"  Tertiary sources: {tertiary_source_count}",
            f"  Direct evidence: {'Yes' if has_direct_evidence else 'No'}",
            f"  Unresolved conflicts: {'Yes' if has_conflicts else 'No'}",
            f"  Exhaustive search: {'Yes' if exhaustive_search else 'No'}",
        ]

        if level < ConfidenceLevel.STRONG:
            lines.append("\nTo improve confidence:")
            if primary_source_count == 0:
                lines.append("  - Obtain primary sources (civil records, parish registers)")
            if not exhaustive_search:
                lines.append("  - Conduct more exhaustive research")
            if has_conflicts:
                lines.append("  - Resolve conflicting evidence")
            if not has_direct_evidence:
                lines.append("  - Find direct evidence for the claim")

        return "\n".join(lines)

    @kernel_function(
        name="correlate_evidence",
        description="Check if multiple pieces of evidence are consistent with each other",
    )
    def correlate_evidence(
        self,
        evidence_descriptions: Annotated[str, "Semicolon-separated descriptions of evidence pieces"],
    ) -> str:
        """
        Check if multiple pieces of evidence are consistent.

        Input should be semicolon-separated evidence descriptions.
        Example: "Birth record shows 1895; Census says age 5 in 1900; Death record says age 67 in 1962"
        """
        # Parse evidence
        pieces = [e.strip() for e in evidence_descriptions.split(";") if e.strip()]

        if len(pieces) < 2:
            return "Need at least 2 pieces of evidence to correlate."

        # Convert to dict format for GPS correlator
        evidence_list = [
            {"description": piece, "source": f"Evidence {i+1}"}
            for i, piece in enumerate(pieces)
        ]

        result = self._gps.correlate_evidence(evidence_list)

        lines = [
            f"Evidence Correlation Analysis:",
            f"  Consistent: {'Yes' if result.is_consistent else 'No'}",
            f"  Confidence: {result.confidence.name}",
        ]

        if result.conflicts:
            lines.append("\nConflicts detected:")
            for conflict in result.conflicts:
                lines.append(f"  - {conflict}")

        lines.append("\nEvidence analyzed:")
        for piece in pieces:
            lines.append(f"  - {piece}")

        return "\n".join(lines)

    @kernel_function(
        name="get_required_searches",
        description="Get list of required searches for a specific event type and location",
    )
    def get_required_searches(
        self,
        event_type: Annotated[str, "Event type: 'birth', 'marriage', 'death', 'immigration'"],
        location: Annotated[str, "Location where event occurred"],
        year: Annotated[int, "Year of the event"],
    ) -> str:
        """
        Get list of required searches for exhaustive research.

        Returns repositories and record types to search.
        """
        searches = self._gps.get_required_searches(event_type, location, year)

        lines = [
            f"Required searches for {event_type} in {location} ({year}):\n",
            "To meet GPS exhaustive research requirement, search these sources:\n",
        ]

        for i, search in enumerate(searches, 1):
            lines.append(f"{i}. {search}")

        lines.append("\nNote: Mark negative results (nothing found) in your research log.")

        return "\n".join(lines)

    @kernel_function(
        name="explain_gps",
        description="Explain the Genealogical Proof Standard (GPS) requirements",
    )
    def explain_gps(self) -> str:
        """Explain the GPS requirements."""
        return """The Genealogical Proof Standard (GPS) has five elements:

1. REASONABLY EXHAUSTIVE RESEARCH
   - Search all potentially relevant sources
   - Document negative results (what you didn't find)
   - Consider all record types for the time/place

2. COMPLETE AND ACCURATE SOURCE CITATIONS
   - Cite every source used
   - Use standard citation format (Evidence Explained)
   - Include repository information

3. ANALYSIS AND CORRELATION OF EVIDENCE
   - Evaluate each piece of evidence
   - Classify as direct, indirect, or negative
   - Compare information across sources

4. RESOLUTION OF CONFLICTING EVIDENCE
   - Identify all conflicts
   - Explain which evidence is more reliable and why
   - Document your reasoning

5. WRITTEN CONCLUSION
   - State the conclusion clearly
   - Summarize the evidence
   - Explain the reasoning

Source Hierarchy:
- PRIMARY: Created at/near event time (civil registration, census)
- SECONDARY: Derived from primary (published genealogies)
- TERTIARY: Indexes and user trees (Ancestry hints, findagrave)

Remember: A conclusion based solely on tertiary sources is NEVER GPS-compliant."""
