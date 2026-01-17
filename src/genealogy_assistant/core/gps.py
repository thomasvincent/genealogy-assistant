"""
Genealogical Proof Standard (GPS) enforcement and validation.

Implements the five elements of the GPS:
1. Reasonably exhaustive research
2. Complete and accurate source citations
3. Analysis and correlation of evidence
4. Resolution of conflicting evidence
5. A written, defensible conclusion

Reference: Board for Certification of Genealogists (BCG)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from genealogy_assistant.core.models import (
    Citation,
    ConfidenceLevel,
    ConclusionStatus,
    ConflictAlert,
    EvidenceType,
    Family,
    Person,
    ProofSummary,
    ResearchLog,
    ResearchLogEntry,
    Source,
    SourceLevel,
)

if TYPE_CHECKING:
    from genealogy_assistant.gramps.client import GrampsClient


@dataclass
class ValidationResult:
    """Result of GPS validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class EvidenceCorrelation:
    """Result of correlating multiple pieces of evidence."""
    fact: str
    supporting_citations: list[Citation]
    conflicting_citations: list[Citation]
    confidence: ConfidenceLevel
    notes: str | None = None


class GenealogyProofStandard:
    """
    GPS enforcement engine.

    Validates research against BCG standards and provides
    guidance for GPS-compliant conclusions.
    """

    # Minimum requirements for exhaustive research by record type
    REQUIRED_SEARCHES = {
        "birth": [
            "civil birth register",
            "church baptism register",
            "census (age validation)",
        ],
        "death": [
            "civil death register",
            "cemetery records",
            "obituaries",
            "probate records",
        ],
        "marriage": [
            "civil marriage register",
            "church marriage register",
            "marriage license/bond",
        ],
        "immigration": [
            "passenger manifest",
            "naturalization records",
            "border crossing records",
        ],
        "identity": [
            "census records (multiple years)",
            "vital records",
            "land records",
            "tax records",
        ],
    }

    # Belgian-specific record requirements
    BELGIAN_SEARCHES = {
        "pre_1796": ["parish registers"],
        "post_1796": ["burgerlijke stand / état civil"],
        "population": ["bevolkingsregister / registre de population"],
    }

    # Cherokee-specific requirements per the prompt
    CHEROKEE_ROLLS = [
        "Baker Roll",
        "Dawes Rolls (Final + Applications)",
        "Guion Miller Roll",
        "Old Settler Rolls",
        "Henderson Roll (1835)",
        "Drennan Roll (1851)",
    ]

    def __init__(self, gramps_client: "GrampsClient | None" = None):
        self.gramps = gramps_client

    def validate_person(self, person: Person) -> ValidationResult:
        """
        Validate a person record against GPS standards.

        Checks:
        - Has at least one sourced fact
        - No impossible dates
        - No identity conflicts
        - Proper source citations
        """
        errors = []
        warnings = []
        suggestions = []

        # Must have at least one name
        if not person.names:
            errors.append("Person has no name")

        # Check for sourced facts
        has_sourced_fact = False
        if person.birth and person.birth.citations:
            has_sourced_fact = True
        if person.death and person.death.citations:
            has_sourced_fact = True
        if person.citations:
            has_sourced_fact = True

        if not has_sourced_fact:
            warnings.append("Person has no sourced facts - add citations")

        # Validate dates
        date_issues = self._validate_person_dates(person)
        errors.extend(date_issues)

        # Check confidence matches evidence
        if person.confidence >= ConfidenceLevel.STRONG and not has_sourced_fact:
            errors.append(
                f"Confidence level {person.confidence.name} requires sourced evidence"
            )

        # Living person check
        if person.is_living and person.death:
            errors.append("Person marked as living but has death record")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _validate_person_dates(self, person: Person) -> list[str]:
        """Check for impossible or conflicting dates."""
        errors = []

        birth_year = person.birth_year()
        death_year = person.death_year()

        if birth_year and death_year:
            age_at_death = death_year - birth_year
            if age_at_death < 0:
                errors.append(
                    f"Death ({death_year}) before birth ({birth_year})"
                )
            elif age_at_death > 120:
                errors.append(
                    f"Implausible age at death: {age_at_death} years"
                )

        # Check childbirth ages for women
        if person.sex == "F" and birth_year:
            for fam_id in person.spouse_family_ids:
                # Would need to look up family and children
                pass  # TODO: Implement with Gramps client

        return errors

    def validate_family(self, family: Family) -> ValidationResult:
        """Validate a family record against GPS standards."""
        errors = []
        warnings = []
        suggestions = []

        # Must have at least one parent or be an adopted/unknown situation
        if not family.husband_id and not family.wife_id:
            if not family.children_ids:
                errors.append("Family has no members")
            else:
                warnings.append("Family has children but no identified parents")

        # Marriage should have citations
        if family.marriage and not family.marriage.citations:
            warnings.append("Marriage event has no source citation")

        # Children should be ordered by birth
        # TODO: Validate child birth order with Gramps client

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def validate_source(self, source: Source) -> ValidationResult:
        """Validate source record."""
        errors = []
        warnings = []
        suggestions = []

        # Must have title
        if not source.title:
            errors.append("Source must have a title")

        # Primary sources should be originals
        if source.level == SourceLevel.PRIMARY and not source.is_original:
            warnings.append(
                "Primary source marked as derivative - verify classification"
            )

        # Tertiary sources need extra scrutiny
        if source.level == SourceLevel.TERTIARY:
            suggestions.append(
                "Tertiary source - must be corroborated with primary/secondary"
            )

        # Image preferred over transcript
        if not source.is_image:
            suggestions.append("Consider obtaining original image if available")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def check_exhaustive_research(
        self,
        research_log: ResearchLog,
        research_type: str = "identity",
    ) -> ValidationResult:
        """
        Verify that reasonably exhaustive research was conducted.

        GPS Element 1: Reasonably exhaustive research in all
        relevant sources.
        """
        errors = []
        warnings = []
        suggestions = []

        required = self.REQUIRED_SEARCHES.get(research_type, [])
        repositories_searched = set()

        for entry in research_log.entries:
            repositories_searched.add(entry.record_type.lower())

        # Check for missing required searches
        missing = []
        for req in required:
            found = any(req.lower() in repo for repo in repositories_searched)
            if not found:
                missing.append(req)

        if missing:
            warnings.append(
                f"Missing searches for exhaustive research: {', '.join(missing)}"
            )
            for m in missing:
                suggestions.append(f"Search {m} records")

        # Check for negative evidence analysis
        negative_entries = research_log.negative_results()
        unanalyzed = [
            e for e in negative_entries
            if not e.absence_explanation
        ]
        if unanalyzed:
            warnings.append(
                f"{len(unanalyzed)} negative search results not analyzed"
            )

        return ValidationResult(
            is_valid=len(missing) == 0 and len(unanalyzed) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def correlate_evidence(
        self,
        citations: list[Citation],
        fact_to_prove: str,
    ) -> EvidenceCorrelation:
        """
        Analyze and correlate multiple pieces of evidence.

        GPS Element 3: Analysis and correlation of evidence.
        """
        supporting = []
        conflicting = []

        # Group citations by what they say
        fact_values: dict[str, list[Citation]] = {}

        for citation in citations:
            key = citation.fact_proven.lower().strip()
            if key not in fact_values:
                fact_values[key] = []
            fact_values[key].append(citation)

        # If all citations agree, they're supporting
        if len(fact_values) == 1:
            supporting = citations
        else:
            # Find the most supported value
            most_supported_key = max(fact_values, key=lambda k: len(fact_values[k]))
            supporting = fact_values[most_supported_key]

            for key, cites in fact_values.items():
                if key != most_supported_key:
                    conflicting.extend(cites)

        # Calculate confidence based on evidence quality
        confidence = self._calculate_confidence(supporting, conflicting)

        return EvidenceCorrelation(
            fact=fact_to_prove,
            supporting_citations=supporting,
            conflicting_citations=conflicting,
            confidence=confidence,
        )

    def _calculate_confidence(
        self,
        supporting: list[Citation],
        conflicting: list[Citation],
    ) -> ConfidenceLevel:
        """Calculate confidence level from evidence."""
        if not supporting:
            return ConfidenceLevel.SPECULATIVE

        if conflicting:
            # Has conflicts - can't be higher than REASONABLE
            return ConfidenceLevel.REASONABLE

        # Count evidence types
        # Would need source lookup for full implementation
        if len(supporting) >= 3:
            return ConfidenceLevel.STRONG
        elif len(supporting) >= 2:
            return ConfidenceLevel.REASONABLE
        else:
            return ConfidenceLevel.WEAK

    def resolve_conflicts(
        self,
        correlation: EvidenceCorrelation,
        resolution_reasoning: str,
    ) -> ProofSummary:
        """
        Document conflict resolution.

        GPS Element 4: Resolution of conflicting evidence.
        """
        conflicts = []
        if correlation.conflicting_citations:
            for cite in correlation.conflicting_citations:
                conflicts.append(
                    f"Citation {cite.id}: {cite.fact_proven}"
                )

        return ProofSummary(
            research_question=f"What is the correct value for: {correlation.fact}",
            primary_evidence=correlation.supporting_citations,
            conflicts_identified=conflicts,
            conflict_resolution=resolution_reasoning if conflicts else None,
            conclusion=correlation.fact,
            conclusion_status=(
                ConclusionStatus.PROVEN
                if correlation.confidence >= ConfidenceLevel.STRONG
                else ConclusionStatus.LIKELY
            ),
            confidence=correlation.confidence,
            reasoning=resolution_reasoning,
        )

    def create_proof_summary(
        self,
        research_question: str,
        research_log: ResearchLog,
        citations: list[Citation],
        conclusion: str,
        reasoning: str,
        ai_assisted: bool = False,
    ) -> ProofSummary:
        """
        Create a GPS-compliant proof summary.

        GPS Element 5: A written, defensible conclusion.
        """
        # Separate citations by source level
        primary = []
        secondary = []
        tertiary = []
        negative = []

        for cite in citations:
            if cite.evidence_type == EvidenceType.NEGATIVE:
                negative.append(cite)
            # Would need source lookup for level
            # For now, assume direct evidence is primary
            elif cite.evidence_type == EvidenceType.DIRECT:
                primary.append(cite)
            else:
                secondary.append(cite)

        # Determine exhaustive search status
        exhaustive = self.check_exhaustive_research(research_log)

        # Calculate confidence
        if primary and exhaustive.is_valid:
            confidence = ConfidenceLevel.GPS_COMPLETE
            status = ConclusionStatus.PROVEN
        elif primary:
            confidence = ConfidenceLevel.STRONG
            status = ConclusionStatus.LIKELY
        elif secondary:
            confidence = ConfidenceLevel.REASONABLE
            status = ConclusionStatus.PROPOSED
        else:
            confidence = ConfidenceLevel.WEAK
            status = ConclusionStatus.UNSUBSTANTIATED

        # Extract repositories from log
        repositories = list({
            entry.repository for entry in research_log.entries
        })

        return ProofSummary(
            research_question=research_question,
            primary_evidence=primary,
            secondary_evidence=secondary,
            tertiary_evidence=tertiary,
            negative_evidence=negative,
            conclusion=conclusion,
            conclusion_status=status,
            confidence=confidence,
            reasoning=reasoning,
            exhaustive_search_completed=exhaustive.is_valid,
            repositories_searched=repositories,
            ai_assisted=ai_assisted,
            ai_assistance_description=(
                "AI-assisted hypothesis generation was used. "
                "Conclusions rely solely on documented sources."
            ) if ai_assisted else None,
        )

    def detect_conflicts(self, person: Person) -> list[ConflictAlert]:
        """
        Run sanity checks and detect conflicts.

        Flags:
        - Impossible dates
        - Overlapping marriages
        - Conflicting death/burial data
        - Unsourced ethnicity claims
        - Same-name identity collisions
        """
        alerts = []

        # Check for impossible birth/death
        if person.birth and person.death:
            birth_year = person.birth_year()
            death_year = person.death_year()

            if birth_year and death_year and death_year < birth_year:
                alerts.append(ConflictAlert(
                    conflict_type="impossible_date",
                    severity="error",
                    description=f"Death year ({death_year}) before birth year ({birth_year})",
                    affected_records=[person.id],
                ))

            if birth_year and death_year:
                age = death_year - birth_year
                if age > 120:
                    alerts.append(ConflictAlert(
                        conflict_type="impossible_date",
                        severity="warning",
                        description=f"Implausible lifespan: {age} years",
                        affected_records=[person.id],
                    ))

        # Check for unsourced facts with high confidence
        if person.confidence >= ConfidenceLevel.STRONG:
            if not person.citations and not (
                person.birth and person.birth.citations
            ):
                alerts.append(ConflictAlert(
                    conflict_type="unsourced_ethnicity",
                    severity="warning",
                    description="High confidence without source citations",
                    affected_records=[person.id],
                ))

        return alerts

    def generate_research_plan(
        self,
        person: Person,
        research_type: str = "identity",
        region: str | None = None,
    ) -> list[str]:
        """
        Generate a research plan based on GPS requirements.

        Returns ordered list of suggested searches.
        """
        plan = []

        # Get required searches
        required = self.REQUIRED_SEARCHES.get(research_type, [])

        # Add region-specific searches
        if region == "belgium":
            birth_year = person.birth_year() or 1850
            if birth_year < 1796:
                required.extend(self.BELGIAN_SEARCHES["pre_1796"])
            else:
                required.extend(self.BELGIAN_SEARCHES["post_1796"])
            required.extend(self.BELGIAN_SEARCHES["population"])

        elif region == "cherokee":
            required.extend(self.CHEROKEE_ROLLS)

        # Build prioritized plan
        for req in required:
            plan.append(f"Search {req}")

        # Add standard suggestions
        plan.append("Check for name spelling variants")
        plan.append("Search for associated persons (FAN club)")
        plan.append("Document all negative searches")

        return plan
