"""
AI-powered genealogy research assistant using Semantic Kernel and AutoGen.

Implements BCG/GPS-compliant research methodology with AI augmentation.
Supports multiple LLM providers and multi-agent collaboration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

import semantic_kernel as sk
from semantic_kernel.contents import ChatHistory

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    Person,
    ProofSummary,
    ResearchLog,
    ResearchLogEntry,
)
from genealogy_assistant.kernel.setup import KernelConfig, create_kernel, get_kernel_info


class ResearchMode(Enum):
    """Research mode for the assistant."""
    SIMPLE = "simple"      # Single agent, direct responses
    COLLABORATIVE = "collaborative"  # Multi-agent with specialists


@dataclass
class AssistantConfig:
    """Configuration for the AI research assistant."""

    # LLM configuration (used by Semantic Kernel)
    llm_provider: str = "anthropic"  # anthropic, openai, azure, ollama
    model: str | None = None  # Uses provider default if None
    temperature: float = 0.3  # Lower for more precise, factual responses

    # Research mode
    mode: ResearchMode = ResearchMode.SIMPLE

    # Plugin configuration
    enable_search: bool = True
    enable_gedcom: bool = True
    enable_gps: bool = True
    enable_reports: bool = True
    enable_memory: bool = True

    # Memory persistence
    memory_directory: str = "./genealogy_memory"

    # Search providers
    search_providers: list[str] = field(
        default_factory=lambda: ["familysearch", "geneanet", "findagrave"]
    )

    # Multi-agent configuration (for COLLABORATIVE mode)
    max_agent_rounds: int = 20
    speaker_selection: str = "auto"

    @classmethod
    def from_legacy(
        cls,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs,
    ) -> AssistantConfig:
        """Create config from legacy API parameters."""
        # Map legacy model names to new format
        provider = "anthropic"
        if model.startswith("gpt"):
            provider = "openai"

        return cls(
            llm_provider=provider,
            model=model,
            temperature=temperature,
            **kwargs,
        )


@dataclass
class ResearchTask:
    """A genealogy research task."""

    task_type: Literal["identify", "verify", "extend", "resolve"]
    description: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    target_person: Person | None = None
    known_facts: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
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
    search_results: list[Any] = field(default_factory=list)

    # New: Multi-agent conversation details
    agent_contributions: dict[str, str] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)


# GPS-compliant system prompt (used for simple mode)
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


class GenealogyAssistant:
    """
    AI-powered genealogy research assistant.

    Uses Semantic Kernel for LLM abstraction and plugins,
    with optional AutoGen multi-agent collaboration.
    """

    def __init__(self, config: AssistantConfig | None = None):
        """Initialize the genealogy assistant."""
        self.config = config or AssistantConfig()
        self._kernel: sk.Kernel | None = None
        self._chat_history: ChatHistory | None = None

        # AutoGen agents (for collaborative mode)
        self._agents: dict | None = None
        self._group_chat = None
        self._model_client = None

        # Active research
        self._current_task: ResearchTask | None = None
        self._research_log: ResearchLog | None = None

    async def connect(self) -> None:
        """Initialize Semantic Kernel and optionally AutoGen agents."""
        # Create kernel configuration
        kernel_config = KernelConfig(
            llm_provider=self.config.llm_provider,
            model=self.config.model,
            temperature=self.config.temperature,
            enable_memory=self.config.enable_memory,
            memory_persist_directory=self.config.memory_directory,
            enable_search_plugins=self.config.enable_search,
            enable_gedcom_plugin=self.config.enable_gedcom,
            enable_gps_plugin=self.config.enable_gps,
            enable_report_plugins=self.config.enable_reports,
            search_providers=self.config.search_providers,
        )

        # Create kernel with plugins
        self._kernel = await create_kernel(kernel_config)
        self._chat_history = ChatHistory(system_message=SYSTEM_PROMPT)

        # Initialize AutoGen agents for collaborative mode
        if self.config.mode == ResearchMode.COLLABORATIVE:
            await self._init_agents()

    async def _init_agents(self) -> None:
        """Initialize AutoGen multi-agent system."""
        from genealogy_assistant.agents.config import (
            create_genealogy_agents,
            create_research_group_chat,
        )
        from genealogy_assistant.agents.llm_config import get_llm_config, create_model_client

        # Get LLM config for AutoGen
        llm_config = get_llm_config(
            provider=self.config.llm_provider,
            model=self.config.model,
            temperature=self.config.temperature,
        )

        # Create model client for group chat
        model_client = create_model_client(
            provider=self.config.llm_provider,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        self._model_client = model_client

        # Create agents with SK tools registered
        self._agents = create_genealogy_agents(llm_config, self._kernel)

        # Create group chat
        self._group_chat = create_research_group_chat(
            self._agents,
            model_client=model_client,
            max_rounds=self.config.max_agent_rounds,
        )

    async def close(self) -> None:
        """Close connections and cleanup."""
        self._kernel = None
        self._agents = None
        self._group_chat = None
        self._model_client = None

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
        if not self._kernel:
            await self.connect()

        if self.config.mode == ResearchMode.COLLABORATIVE:
            return await self._research_collaborative(question, context)
        else:
            return await self._research_simple(question, context)

    async def _research_simple(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """Single-agent research using Semantic Kernel."""
        # Build context message
        user_message = question
        if context:
            user_message += f"\n\nContext:\n{json.dumps(context, indent=2, default=str)}"

        # Add to chat history
        self._chat_history.add_user_message(user_message)

        # Get chat completion service
        chat_service = self._kernel.get_service("chat")

        # Execute with plugin functions available
        settings = self._kernel.get_prompt_execution_settings_class("chat")()
        settings.temperature = self.config.temperature

        # Get response from LLM with function calling
        result = await chat_service.get_chat_message_content(
            chat_history=self._chat_history,
            settings=settings,
            kernel=self._kernel,
        )

        assistant_message = str(result)
        self._chat_history.add_assistant_message(assistant_message)

        return self._parse_response(assistant_message)

    async def _research_collaborative(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """Multi-agent research using AutoGen GroupChat."""
        from autogen_agentchat.messages import TextMessage

        # Build context message
        message = question
        if context:
            message += f"\n\nContext:\n{json.dumps(context, indent=2, default=str)}"

        # Create task message
        task = TextMessage(content=message, source="user")

        # Run the group chat
        contributions = {}
        final_message = ""

        async for event in self._group_chat.run_stream(task=task):
            # Collect agent contributions
            if hasattr(event, "source") and hasattr(event, "content"):
                sender = event.source
                content = str(event.content)
                if sender not in contributions:
                    contributions[sender] = ""
                contributions[sender] += content + "\n"
                final_message = content  # Track last message

        response = self._parse_response(final_message)
        response.agent_contributions = contributions

        return response

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

        Combines database search with AI analysis using the search plugin.
        """
        if not self._kernel:
            await self.connect()

        # Build search parameters
        search_params = {"surname": surname}
        if given_name:
            search_params["given_name"] = given_name
        if birth_year:
            search_params["birth_year"] = birth_year
        if birth_place:
            search_params["birth_place"] = birth_place

        # Invoke search plugin
        search_result = await self._kernel.invoke(
            plugin_name="search",
            function_name="search_person",
            **search_params,
        )

        # Ask AI to analyze results
        question = f"""Analyze these search results for {given_name or ''} {surname}:

{search_result}

Evaluate:
1. Which results are most likely matches?
2. Are there any identity conflicts?
3. What sources have primary vs. secondary evidence?
4. What additional searches would help verify identity?"""

        response = await self.research(question)
        response.tools_used.append("search.search_person")

        return response

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

        Uses the GPS validation plugin for automated checking.
        """
        if not self._kernel:
            await self.connect()

        # Use GPS plugin for initial validation
        gps_result = await self._kernel.invoke(
            plugin_name="gps",
            function_name="validate_proof",
            conclusion=conclusion,
            evidence="; ".join(evidence),
        )

        # Get AI analysis
        evidence_text = "\n".join(f"- {e}" for e in evidence)

        question = f"""Evaluate this genealogical conclusion against GPS standards:

CONCLUSION: {conclusion}

EVIDENCE:
{evidence_text}

GPS AUTOMATED CHECK:
{gps_result}

Assess:
1. Does the evidence meet GPS requirements?
2. Is the research reasonably exhaustive?
3. Are there conflicts that need resolution?
4. What is the appropriate confidence level (1-5)?
5. What additional evidence would strengthen/disprove this?"""

        response = await self.research(question)
        response.tools_used.append("gps.validate_proof")

        return response

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

    async def generate_proof_summary(
        self,
        research_question: str,
        conclusion: str,
        evidence: list[str],
        confidence: int,
        conflicts: list[str] | None = None,
    ) -> str:
        """
        Generate a GPS-compliant proof summary.

        Uses the reports plugin for formatting.
        """
        if not self._kernel:
            await self.connect()

        result = await self._kernel.invoke(
            plugin_name="reports",
            function_name="generate_proof_summary",
            research_question=research_question,
            conclusion=conclusion,
            evidence="; ".join(evidence),
            confidence=confidence,
            conflicts="; ".join(conflicts) if conflicts else None,
        )

        return str(result)

    async def format_citation(
        self,
        record_type: str,
        **kwargs,
    ) -> str:
        """
        Format a source citation using Evidence Explained standards.

        Uses the citations plugin for formatting.
        """
        if not self._kernel:
            await self.connect()

        # Determine citation function based on record type
        function_map = {
            "vital": "format_vital_record_citation",
            "census": "format_census_citation",
            "parish": "format_parish_register_citation",
            "online": "format_online_database_citation",
        }

        func_name = function_map.get(record_type, "format_vital_record_citation")

        result = await self._kernel.invoke(
            plugin_name="citations",
            function_name=func_name,
            **kwargs,
        )

        return str(result)

    async def remember_person(
        self,
        person_name: str,
        **kwargs,
    ) -> str:
        """
        Store information about a person in memory.

        Uses the memory plugin for persistence.
        """
        if not self._kernel:
            await self.connect()

        result = await self._kernel.invoke(
            plugin_name="memory",
            function_name="remember_person",
            person_name=person_name,
            **kwargs,
        )

        return str(result)

    async def recall_person(
        self,
        query: str,
        limit: int = 5,
    ) -> str:
        """
        Search memory for information about a person.

        Uses semantic search over stored person data.
        """
        if not self._kernel:
            await self.connect()

        result = await self._kernel.invoke(
            plugin_name="memory",
            function_name="recall_person",
            query=query,
            limit=limit,
        )

        return str(result)

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self._chat_history = ChatHistory(system_message=SYSTEM_PROMPT)

    def get_kernel_info(self) -> dict:
        """Get information about loaded kernel plugins and services."""
        if not self._kernel:
            return {"status": "not_connected"}
        return get_kernel_info(self._kernel)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False


# Backward compatibility alias
async def create_assistant(
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    **kwargs,
) -> GenealogyAssistant:
    """
    Create a genealogy assistant with legacy-style configuration.

    Provided for backward compatibility with existing code.
    """
    config = AssistantConfig.from_legacy(
        api_key=api_key,
        model=model,
        **kwargs,
    )
    assistant = GenealogyAssistant(config)
    await assistant.connect()
    return assistant
