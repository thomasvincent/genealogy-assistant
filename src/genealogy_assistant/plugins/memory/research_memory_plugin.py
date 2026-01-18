"""Research memory plugin for Semantic Kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from semantic_kernel.functions import kernel_function

if TYPE_CHECKING:
    from semantic_kernel.memory import SemanticTextMemory


class ResearchMemoryPlugin:
    """
    Persistent memory for genealogy research.

    Stores and retrieves research findings, person information,
    and conclusions across sessions.
    """

    def __init__(self, memory: "SemanticTextMemory"):
        """
        Initialize the research memory plugin.

        Args:
            memory: Semantic Kernel memory instance
        """
        self._memory = memory
        self._collections = {
            "persons": "genealogy_persons",
            "sources": "genealogy_sources",
            "research": "genealogy_research",
            "conclusions": "genealogy_conclusions",
        }

    @kernel_function(
        name="remember_person",
        description="Store information about a person for later retrieval",
    )
    async def remember_person(
        self,
        person_name: Annotated[str, "Full name of the person"],
        birth_info: Annotated[str | None, "Birth date and place"] = None,
        death_info: Annotated[str | None, "Death date and place"] = None,
        relationships: Annotated[str | None, "Known relationships"] = None,
        sources: Annotated[str | None, "Sources for this information"] = None,
        notes: Annotated[str | None, "Additional notes"] = None,
    ) -> str:
        """
        Store information about a person in memory.

        This information can be recalled later for research.
        """
        text_parts = [f"Person: {person_name}"]

        if birth_info:
            text_parts.append(f"Birth: {birth_info}")
        if death_info:
            text_parts.append(f"Death: {death_info}")
        if relationships:
            text_parts.append(f"Relationships: {relationships}")
        if sources:
            text_parts.append(f"Sources: {sources}")
        if notes:
            text_parts.append(f"Notes: {notes}")

        text = "\n".join(text_parts)
        person_id = str(uuid4())

        await self._memory.save_information(
            collection=self._collections["persons"],
            id=person_id,
            text=text,
        )

        return f"Remembered {person_name} (ID: {person_id})"

    @kernel_function(
        name="recall_person",
        description="Search memory for information about a person",
    )
    async def recall_person(
        self,
        query: Annotated[str, "Name or description to search for"],
        limit: Annotated[int, "Maximum number of results"] = 5,
    ) -> str:
        """
        Search memory for information about persons.

        Uses semantic search to find relevant stored information.
        """
        results = await self._memory.search(
            collection=self._collections["persons"],
            query=query,
            limit=limit,
        )

        if not results:
            return f"No person information found matching: {query}"

        lines = [f"Found {len(results)} matching person records:\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"--- Result {i} (relevance: {result.relevance:.2f}) ---")
            lines.append(result.text)
            lines.append("")

        return "\n".join(lines)

    @kernel_function(
        name="remember_research",
        description="Store research findings and conclusions",
    )
    async def remember_research(
        self,
        research_question: Annotated[str, "The research question"],
        findings: Annotated[str, "What was found"],
        sources_searched: Annotated[str, "Sources that were searched"],
        confidence: Annotated[str, "Confidence level (1-5)"],
        next_steps: Annotated[str | None, "Recommended next steps"] = None,
    ) -> str:
        """
        Store research findings in memory.

        Allows recalling previous research on similar questions.
        """
        text_parts = [
            f"Research Question: {research_question}",
            f"Findings: {findings}",
            f"Sources Searched: {sources_searched}",
            f"Confidence: {confidence}",
        ]

        if next_steps:
            text_parts.append(f"Next Steps: {next_steps}")

        text = "\n".join(text_parts)
        research_id = str(uuid4())

        await self._memory.save_information(
            collection=self._collections["research"],
            id=research_id,
            text=text,
        )

        return f"Research logged (ID: {research_id})"

    @kernel_function(
        name="recall_research",
        description="Search for previous research on a topic",
    )
    async def recall_research(
        self,
        query: Annotated[str, "Topic or question to search for"],
        limit: Annotated[int, "Maximum number of results"] = 5,
    ) -> str:
        """
        Search memory for previous research.

        Helps avoid duplicate research and build on past findings.
        """
        results = await self._memory.search(
            collection=self._collections["research"],
            query=query,
            limit=limit,
        )

        if not results:
            return f"No previous research found on: {query}"

        lines = [f"Found {len(results)} related research entries:\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"--- Research {i} (relevance: {result.relevance:.2f}) ---")
            lines.append(result.text)
            lines.append("")

        return "\n".join(lines)

    @kernel_function(
        name="remember_source",
        description="Store a source for future reference",
    )
    async def remember_source(
        self,
        source_title: Annotated[str, "Title of the source"],
        source_type: Annotated[str, "Type: 'primary', 'secondary', 'tertiary'"],
        repository: Annotated[str, "Where the source is located"],
        coverage: Annotated[str, "What the source covers (dates, locations)"],
        access_info: Annotated[str | None, "How to access the source"] = None,
    ) -> str:
        """
        Store information about a source for future reference.

        Useful for tracking repositories and record availability.
        """
        text_parts = [
            f"Source: {source_title}",
            f"Type: {source_type}",
            f"Repository: {repository}",
            f"Coverage: {coverage}",
        ]

        if access_info:
            text_parts.append(f"Access: {access_info}")

        text = "\n".join(text_parts)
        source_id = str(uuid4())

        await self._memory.save_information(
            collection=self._collections["sources"],
            id=source_id,
            text=text,
        )

        return f"Source remembered (ID: {source_id})"

    @kernel_function(
        name="recall_sources",
        description="Search for remembered sources",
    )
    async def recall_sources(
        self,
        query: Annotated[str, "Search query (location, record type, etc.)"],
        limit: Annotated[int, "Maximum number of results"] = 5,
    ) -> str:
        """
        Search memory for relevant sources.

        Helps find previously identified repositories and records.
        """
        results = await self._memory.search(
            collection=self._collections["sources"],
            query=query,
            limit=limit,
        )

        if not results:
            return f"No sources found matching: {query}"

        lines = [f"Found {len(results)} relevant sources:\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"--- Source {i} (relevance: {result.relevance:.2f}) ---")
            lines.append(result.text)
            lines.append("")

        return "\n".join(lines)

    @kernel_function(
        name="save_conclusion",
        description="Save a GPS-compliant conclusion for a research question",
    )
    async def save_conclusion(
        self,
        research_question: Annotated[str, "The research question answered"],
        conclusion: Annotated[str, "The GPS-compliant conclusion"],
        confidence_level: Annotated[int, "Confidence level 1-5"],
        key_evidence: Annotated[str, "Key pieces of evidence supporting conclusion"],
    ) -> str:
        """
        Save a formal conclusion for future reference.

        Conclusions can be recalled when researching related questions.
        """
        text = f"""Research Question: {research_question}

Conclusion: {conclusion}

Confidence Level: {confidence_level}/5

Key Evidence:
{key_evidence}"""

        conclusion_id = str(uuid4())

        await self._memory.save_information(
            collection=self._collections["conclusions"],
            id=conclusion_id,
            text=text,
        )

        return f"Conclusion saved (ID: {conclusion_id})"

    @kernel_function(
        name="recall_conclusions",
        description="Search for previous conclusions on a topic",
    )
    async def recall_conclusions(
        self,
        query: Annotated[str, "Topic or person to search for"],
        limit: Annotated[int, "Maximum number of results"] = 3,
    ) -> str:
        """
        Search for previous conclusions.

        Helps maintain consistency and avoid contradictory conclusions.
        """
        results = await self._memory.search(
            collection=self._collections["conclusions"],
            query=query,
            limit=limit,
        )

        if not results:
            return f"No previous conclusions found for: {query}"

        lines = [f"Found {len(results)} related conclusions:\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"--- Conclusion {i} (relevance: {result.relevance:.2f}) ---")
            lines.append(result.text)
            lines.append("")

        return "\n".join(lines)
