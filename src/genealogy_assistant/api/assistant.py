"""
AI-powered genealogy research assistant using Claude.

Implements BCG/GPS-compliant research methodology with AI augmentation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from anthropic import AsyncAnthropic

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    ConclusionStatus,
    Person,
    ProofSummary,
    ResearchLog,
    ResearchLogEntry,
    Source,
    SourceLevel,
)
from genealogy_assistant.core.gps import GenealogyProofStandard
from genealogy_assistant.search.unified import UnifiedSearch, UnifiedSearchConfig


# GPS-compliant system prompt
SYSTEM_PROMPT = """You are the Lead Genealogical Research Consultant, operating at a standard equivalent to a Board for Certification of Genealogists (BCG)–certified professional.

You are meticulous, skeptical, evidence-first, and intolerant of unsourced claims, identity conflation, or speculative lineage building.

Your expertise includes:
- Transatlantic genealogy (18th–20th centuries)
- Migration from Belgium, the Netherlands, Germany to the United States
- Cherokee genealogy using roll-based proof
- Irish, Scottish, English, and Channel Islands genealogy
- Paleography (Dutch, French, German, Latin; Kurrent/Sütterlin)
- Jurisdictional transitions (parish → civil)
- GEDCOM 5.5.1 / 7.0 data integrity

## Core Methodology — Genealogical Proof Standard (GPS)

All conclusions must comply with the Genealogical Proof Standard:
1. Reasonably exhaustive research
2. Complete and accurate source citations
3. Analysis and correlation of evidence
4. Resolution of conflicting evidence
5. A written, defensible conclusion

Conclusions must be labeled as: Proven, Likely, Proposed, Disproven, or Unsubstantiated Family Lore.

## Source Hierarchy (STRICT ENFORCEMENT)

1️⃣ PRIMARY: Created at/near time of event (civil registration, parish registers, census)
2️⃣ SECONDARY: Derived from primary (county histories, published genealogies)
3️⃣ TERTIARY: Indexes, databases, user trees (AccessGenealogy, Ancestry trees)

Rules:
- Primary sources always first
- Tertiary sources may never stand alone
- Original images > transcripts > indexes

## Output Structure

All responses must include:
1. Extracted Facts (with sources)
2. Research Log (new entries)
3. Analysis & Correlation
4. Conflicts & Resolution
5. Proof Summary (if concluding)
6. Confidence Score (1-5)
7. Next Research Actions

If AI assists reasoning, state: "AI-assisted hypothesis generation was used. Conclusions rely solely on documented sources."

You now operate under this system at all times."""


@dataclass
class AssistantConfig:
    """Configuration for the AI research assistant."""
    api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.3  # Lower for more precise, factual responses

    # Search configuration
    search_config: UnifiedSearchConfig | None = None

    # Research log persistence
    log_path: str | None = None


@dataclass
class ResearchTask:
    """A genealogy research task."""
    # Required fields (no defaults) must come first
    task_type: Literal["identify", "verify", "extend", "resolve"]
    description: str

    # Optional fields with defaults
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    target_person: Person | None = None

    # Research context
    known_facts: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)

    # Results
    research_log: ResearchLog | None = None
    proof_summary: ProofSummary | None = None
    status: Literal["pending", "in_progress", "completed", "blocked"] = "pending"


@dataclass
class AssistantResponse:
    """Response from the AI assistant."""
    message: str
    research_log_entries: list[ResearchLogEntry] = field(default_factory=list)
    proof_summary: ProofSummary | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.REASONABLE
    next_actions: list[str] = field(default_factory=list)
    ai_assisted: bool = True

    # Search results if any
    search_results: list[Any] = field(default_factory=list)


class GenealogyAssistant:
    """
    AI-powered genealogy research assistant.

    Uses Claude API with GPS-compliant methodology to assist
    with genealogical research.
    """

    def __init__(self, config: AssistantConfig | None = None):
        """Initialize the genealogy assistant."""
        self.config = config or AssistantConfig()
        self._client: AsyncAnthropic | None = None
        self._search: UnifiedSearch | None = None
        self._gps = GenealogyProofStandard()

        # Conversation history
        self._messages: list[dict] = []

        # Active research
        self._current_task: ResearchTask | None = None
        self._research_log: ResearchLog | None = None

    async def connect(self) -> None:
        """Initialize API client and search providers."""
        if self.config.api_key:
            self._client = AsyncAnthropic(api_key=self.config.api_key)
        else:
            # Will use ANTHROPIC_API_KEY environment variable
            self._client = AsyncAnthropic()

        # Initialize search
        self._search = UnifiedSearch(self.config.search_config)
        await self._search.connect()

    async def close(self) -> None:
        """Close connections."""
        if self._search:
            await self._search.close()

    async def research(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """
        Conduct research on a genealogical question.

        Args:
            question: The research question
            context: Additional context (known facts, sources, etc.)

        Returns:
            AssistantResponse with findings and next steps
        """
        if not self._client:
            await self.connect()

        # Build context message
        context_text = ""
        if context:
            context_text = f"\n\nContext:\n{json.dumps(context, indent=2, default=str)}"

        # Add user message
        self._messages.append({
            "role": "user",
            "content": f"{question}{context_text}",
        })

        # Call Claude API
        response = await self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=SYSTEM_PROMPT,
            messages=self._messages,
        )

        # Extract response text
        assistant_message = response.content[0].text

        # Add to history
        self._messages.append({
            "role": "assistant",
            "content": assistant_message,
        })

        # Parse response for structured data
        return self._parse_response(assistant_message)

    def _parse_response(self, message: str) -> AssistantResponse:
        """Parse assistant response for structured data."""
        response = AssistantResponse(
            message=message,
            ai_assisted=True,
        )

        # Extract confidence level if mentioned
        confidence_patterns = {
            "confidence: 5": ConfidenceLevel.GPS_COMPLETE,
            "confidence: 4": ConfidenceLevel.STRONG,
            "confidence: 3": ConfidenceLevel.REASONABLE,
            "confidence: 2": ConfidenceLevel.WEAK,
            "confidence: 1": ConfidenceLevel.SPECULATIVE,
            "gps-complete": ConfidenceLevel.GPS_COMPLETE,
            "proven": ConfidenceLevel.GPS_COMPLETE,
            "likely": ConfidenceLevel.STRONG,
            "proposed": ConfidenceLevel.REASONABLE,
            "speculative": ConfidenceLevel.SPECULATIVE,
        }

        message_lower = message.lower()
        for pattern, level in confidence_patterns.items():
            if pattern in message_lower:
                response.confidence = level
                break

        # Extract next actions
        if "next" in message_lower or "recommend" in message_lower:
            lines = message.split("\n")
            for i, line in enumerate(lines):
                if "next" in line.lower() or "recommend" in line.lower():
                    # Collect following bullet points
                    for next_line in lines[i + 1:]:
                        if next_line.strip().startswith(("-", "*", "•", "1", "2", "3")):
                            action = next_line.strip().lstrip("-*•0123456789. ")
                            if action:
                                response.next_actions.append(action)
                        elif next_line.strip() and not next_line.strip().startswith(("#", "##")):
                            break

        return response

    async def search_and_analyze(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
        providers: list[str] | None = None,
    ) -> AssistantResponse:
        """
        Search genealogy databases and analyze results.

        Combines database search with AI analysis.
        """
        if not self._search:
            await self.connect()

        # Execute search
        search_response = await self._search.search_person(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=birth_place,
            providers=providers,
        )

        # Format results for AI analysis
        results_text = self._format_search_results(search_response.results[:20])

        # Ask AI to analyze
        question = f"""Analyze these search results for {given_name or ''} {surname}:

{results_text}

Evaluate:
1. Which results are most likely matches?
2. Are there any identity conflicts?
3. What sources have primary vs. secondary evidence?
4. What additional searches would help verify identity?"""

        response = await self.research(question)
        response.search_results = search_response.results

        return response

    def _format_search_results(self, results: list[Any]) -> str:
        """Format search results for AI analysis."""
        if not results:
            return "No results found."

        lines = []
        for i, result in enumerate(results, 1):
            parts = [f"{i}. {result.given_name} {result.surname}"]

            if result.birth_date:
                parts.append(f"b. {result.birth_date.to_gedcom()}")
            if result.death_date:
                parts.append(f"d. {result.death_date.to_gedcom()}")
            if result.birth_place:
                parts.append(f"in {result.birth_place.name}")

            parts.append(f"[{result.provider}]")
            parts.append(f"({result.source_level.value})")

            lines.append(" ".join(parts))

        return "\n".join(lines)

    async def create_research_plan(
        self,
        target_person: Person,
        research_goal: str,
    ) -> AssistantResponse:
        """
        Create a GPS-compliant research plan.

        Generates a systematic plan for researching a person.
        """
        person_info = self._format_person(target_person)

        question = f"""Create a GPS-compliant research plan for:

{person_info}

Research Goal: {research_goal}

Include:
1. Required searches by source type (primary first)
2. Repositories to check
3. Surname variants to search
4. Expected record types by time period
5. Potential conflicts to watch for"""

        return await self.research(question)

    def _format_person(self, person: Person) -> str:
        """Format person for AI context."""
        lines = []

        if person.primary_name:
            lines.append(f"Name: {person.primary_name.full_name()}")
            if person.primary_name.variants:
                lines.append(f"Variants: {', '.join(person.primary_name.variants)}")

        if person.birth:
            if person.birth.date:
                lines.append(f"Birth: {person.birth.date.to_gedcom()}")
            if person.birth.place:
                lines.append(f"Birthplace: {person.birth.place.name}")

        if person.death:
            if person.death.date:
                lines.append(f"Death: {person.death.date.to_gedcom()}")
            if person.death.place:
                lines.append(f"Deathplace: {person.death.place.name}")

        return "\n".join(lines)

    async def verify_conclusion(
        self,
        conclusion: str,
        evidence: list[str],
    ) -> AssistantResponse:
        """
        Verify a genealogical conclusion against GPS standards.

        Evaluates whether the evidence supports the conclusion.
        """
        evidence_text = "\n".join(f"- {e}" for e in evidence)

        question = f"""Evaluate this genealogical conclusion against GPS standards:

CONCLUSION: {conclusion}

EVIDENCE:
{evidence_text}

Assess:
1. Does the evidence meet GPS requirements?
2. Is the research reasonably exhaustive?
3. Are there conflicts that need resolution?
4. What is the appropriate confidence level (1-5)?
5. What additional evidence would strengthen/disprove this?"""

        return await self.research(question)

    async def generate_archive_letter(
        self,
        archive: str,
        person_name: str,
        records_needed: list[str],
        known_facts: list[str],
    ) -> str:
        """Generate a professional archive request letter."""
        facts_text = "\n".join(f"- {f}" for f in known_facts)
        records_text = "\n".join(f"- {r}" for r in records_needed)

        question = f"""Generate a professional archive request letter to:

Archive: {archive}
Person Researched: {person_name}

Known Facts:
{facts_text}

Records Needed:
{records_text}

Include:
1. Polite salutation
2. Research context
3. Specific record requests with dates
4. Spelling variants to search
5. Payment inquiry
6. Contact information placeholder"""

        response = await self.research(question)
        return response.message

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self._messages = []

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
