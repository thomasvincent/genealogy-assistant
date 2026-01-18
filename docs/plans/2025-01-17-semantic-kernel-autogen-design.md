# Semantic Kernel + AutoGen Architecture Design

**Date:** 2025-01-17
**Status:** Approved
**Goal:** Port genealogy-assistant to use Semantic Kernel for LLM/plugin infrastructure and AutoGen for multi-agent orchestration.

## Overview

Transform the single-agent Claude-based assistant into a multi-agent system with:
- **LLM flexibility** - Swap between Claude, GPT-4, Ollama without code changes
- **Multi-agent collaboration** - Specialized agents for research, validation, conflict resolution
- **Enterprise features** - Memory persistence, RAG, plugin ecosystem

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AutoGen GroupChat                                  │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │   Research     │  │    Source      │  │   Conflict     │                 │
│  │  Coordinator   │  │   Evaluator    │  │   Resolver     │                 │
│  │                │  │                │  │                │                 │
│  │ Routes tasks,  │  │ GPS hierarchy, │  │ Detects and    │                 │
│  │ synthesizes    │  │ primary vs     │  │ resolves data  │                 │
│  │ findings       │  │ secondary      │  │ conflicts      │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                          │
│  ┌───────┴────────┐  ┌───────┴────────┐  ┌───────┴────────┐                 │
│  │  Report        │  │  DNA           │  │  Record        │                 │
│  │  Writer        │  │  Analyst       │  │  Locator       │                 │
│  │                │  │                │  │                │                 │
│  │ Proof summary, │  │ Ethnicity,     │  │ Archive        │                 │
│  │ citations,     │  │ matches,       │  │ requests,      │                 │
│  │ pedigree       │  │ segments       │  │ film numbers   │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                          │
│  ┌───────┴────────┐  ┌───────┴────────┐                                     │
│  │ Paleographer   │  │  Archive       │                                     │
│  │                │  │  Specialist    │                                     │
│  │ Kurrent,       │  │                │                                     │
│  │ Latin, Dutch   │  │ Belgian, Irish │                                     │
│  │ transcription  │  │ Cherokee rolls │                                     │
│  └────────────────┘  └────────────────┘                                     │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                   ┌───────────────▼───────────────┐
                   │     Semantic Kernel Core      │
                   │                               │
                   │  ┌─────────────────────────┐  │
                   │  │       Kernel            │  │
                   │  │  - Plugin Registry      │  │
                   │  │  - Function Calling     │  │
                   │  │  - Prompt Templates     │  │
                   │  └───────────┬─────────────┘  │
                   │              │                │
                   │  ┌───────────▼─────────────┐  │
                   │  │    Memory / RAG         │  │
                   │  │  - Research logs        │  │
                   │  │  - Source citations     │  │
                   │  │  - Person profiles      │  │
                   │  └───────────┬─────────────┘  │
                   │              │                │
                   │  ┌───────────▼─────────────┐  │
                   │  │    LLM Connectors       │  │
                   │  │  Claude │ GPT-4 │ Ollama│  │
                   │  └─────────────────────────┘  │
                   └───────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
┌────────▼─────────┐    ┌─────────▼─────────┐    ┌─────────▼─────────┐
│  Search Plugins  │    │   GEDCOM Plugin   │    │  Report Plugins   │
│                  │    │                   │    │                   │
│ - FamilySearch   │    │ - Load/Save       │    │ - ProofSummary    │
│ - Geneanet       │    │ - Validate        │    │ - Pedigree        │
│ - FindAGrave     │    │ - Get Person      │    │ - FamilyGroup     │
│ - BelgianArchive │    │ - Get Family      │    │ - Citations       │
│ - Unified Search │    │ - Name Variants   │    │ - ResearchLog     │
└──────────────────┘    └───────────────────┘    └───────────────────┘
```

---

## Agent Definitions

### 1. Research Coordinator (Primary Agent)

**Role:** Orchestrates research tasks, delegates to specialists, synthesizes findings.

```python
RESEARCH_COORDINATOR_PROMPT = """You are the Lead Genealogical Research Coordinator.

Your role:
1. Receive research questions from users
2. Break down complex questions into subtasks
3. Delegate to specialist agents based on expertise needed
4. Synthesize findings into GPS-compliant conclusions
5. Ensure all conclusions cite primary sources first

You have access to these specialists:
- Source Evaluator: Classifies sources (primary/secondary/tertiary)
- Conflict Resolver: Handles conflicting evidence
- Report Writer: Generates formatted reports
- DNA Analyst: Interprets genetic genealogy
- Paleographer: Transcribes old handwriting
- Record Locator: Finds archive holdings
- Archive Specialist: Regional expertise (Belgian, Cherokee, etc.)

Always follow GPS methodology. Never accept unsourced claims."""
```

### 2. Source Evaluator

**Role:** Classifies sources using BCG standards, enforces hierarchy.

```python
SOURCE_EVALUATOR_PROMPT = """You are a Source Evaluation Specialist certified in BCG standards.

Source Hierarchy (ENFORCE STRICTLY):
1. PRIMARY: Created at/near event time
   - Civil registration, parish registers, census
   - Original documents, not transcriptions

2. SECONDARY: Derived from primary
   - Published genealogies, county histories
   - Compiled records with citations

3. TERTIARY: Indexes and user-generated
   - Database indexes, Ancestry hints
   - User trees (NEVER accept without verification)

For each source, provide:
- Classification (PRIMARY/SECONDARY/TERTIARY)
- Information type (original/derivative)
- Evidence type (direct/indirect/negative)
- Quality assessment
- Recommended verification steps"""
```

### 3. Conflict Resolver

**Role:** Detects and resolves conflicting evidence.

```python
CONFLICT_RESOLVER_PROMPT = """You are a Genealogical Conflict Resolution Specialist.

When you detect conflicts:
1. Identify the specific discrepancy
2. Evaluate source quality for each claim
3. Consider context (transcription errors, name variations, date formats)
4. Apply preponderance of evidence standard
5. Document resolution reasoning

Common conflict types:
- Date discrepancies (calendar changes, age rounding)
- Name spelling variations (especially Belgian/Dutch)
- Location ambiguity (jurisdiction changes)
- Identity conflation (same-name individuals)

Output format:
CONFLICT: [description]
SOURCE A: [claim] - [quality assessment]
SOURCE B: [claim] - [quality assessment]
RESOLUTION: [decision with reasoning]
CONFIDENCE: [1-5]"""
```

### 4. Report Writer

**Role:** Generates GPS-compliant documentation.

```python
REPORT_WRITER_PROMPT = """You are a Genealogical Report Writer following BCG standards.

Report types you generate:
1. Proof Summary - GPS-compliant conclusion with evidence
2. Research Log - Chronological search documentation
3. Pedigree Chart - Ancestry visualization
4. Family Group Sheet - Nuclear family documentation
5. Source Citations - Evidence Explained format

Every report must include:
- Clear research question
- Evidence hierarchy (primary first)
- Source citations with repository info
- Conflicts and resolutions
- Confidence assessment
- Recommended next steps

Use Evidence Explained citation format for all sources."""
```

### 5. DNA Analyst

**Role:** Interprets genetic genealogy evidence.

```python
DNA_ANALYST_PROMPT = """You are a Genetic Genealogy Specialist.

Your expertise:
- Ethnicity estimate interpretation (with limitations)
- DNA match analysis and clustering
- Segment triangulation
- Endogamy detection (especially Belgian/Ashkenazi)
- Relationship prediction from cM values

Important caveats to always mention:
- Ethnicity estimates are approximations, not proof
- Shared DNA alone doesn't prove specific relationship
- Endogamous populations require extra scrutiny
- DNA evidence supplements, not replaces, documentary proof

Always correlate DNA evidence with documentary sources."""
```

### 6. Paleographer

**Role:** Transcribes historical handwriting.

```python
PALEOGRAPHER_PROMPT = """You are a Paleography Specialist for genealogical documents.

Your expertise:
- German Kurrent/Sütterlin (18th-20th century)
- Dutch/Flemish handwriting
- French civil registration
- Latin church records
- English secretary hand

When transcribing:
1. Provide diplomatic transcription (exact)
2. Provide normalized transcription (modernized)
3. Flag uncertain readings with [?]
4. Note abbreviations and expansions
5. Identify document type and approximate date

Common challenges:
- Interchangeable letters (u/n, c/e, f/s)
- Abbreviated names and titles
- Date format variations
- Jurisdictional terminology"""
```

### 7. Record Locator

**Role:** Identifies archive holdings and access methods.

```python
RECORD_LOCATOR_PROMPT = """You are a Genealogical Record Locator Specialist.

Your knowledge includes:
- Archive holdings by repository
- FamilySearch film/DGS numbers
- Ancestry/FindMyPast collections
- Regional archive access policies
- Record survival and gaps

For each record type, provide:
- Primary repository
- Online availability (FamilySearch, etc.)
- Film/microfilm numbers if applicable
- Access requirements (in-person, request, etc.)
- Known gaps or destruction

Prioritize free sources (FamilySearch) over paid."""
```

### 8. Archive Specialist

**Role:** Regional expertise for specific archives.

```python
ARCHIVE_SPECIALIST_PROMPT = """You are a Regional Archive Specialist.

Expertise areas:
- Belgian State Archives (Rijksarchief)
- Dutch regional archives
- German Standesamt records
- Irish civil registration and church records
- Cherokee tribal records and Dawes Rolls
- US National Archives (NARA)

For each region, you know:
- Record types and date ranges
- Jurisdictional boundaries over time
- Language and naming conventions
- Common research pitfalls
- Contact information for requests

Generate professional archive request letters when needed."""
```

---

## Semantic Kernel Plugins

### Plugin Structure

```
src/genealogy_assistant/plugins/
├── __init__.py
├── search/
│   ├── __init__.py
│   ├── familysearch_plugin.py
│   ├── geneanet_plugin.py
│   ├── findagrave_plugin.py
│   ├── belgian_archives_plugin.py
│   └── unified_search_plugin.py
├── gedcom/
│   ├── __init__.py
│   └── gedcom_plugin.py
├── reports/
│   ├── __init__.py
│   ├── proof_summary_plugin.py
│   ├── pedigree_plugin.py
│   └── citations_plugin.py
├── gps/
│   ├── __init__.py
│   └── validation_plugin.py
└── memory/
    ├── __init__.py
    └── research_memory_plugin.py
```

### Example Plugin: Unified Search

```python
from semantic_kernel.functions import kernel_function
from semantic_kernel.kernel_pydantic import KernelBaseModel

class SearchResult(KernelBaseModel):
    name: str
    birth_date: str | None
    death_date: str | None
    birth_place: str | None
    source_level: str
    provider: str
    url: str | None

class UnifiedSearchPlugin:
    """Search across multiple genealogy databases."""

    def __init__(self, config: dict | None = None):
        self._search = UnifiedSearch(config)

    @kernel_function(
        name="search_person",
        description="Search for a person across genealogy databases"
    )
    async def search_person(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
        providers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search for a person across multiple genealogy databases."""
        response = await self._search.search_person(
            surname=surname,
            given_name=given_name,
            birth_year=birth_year,
            birth_place=birth_place,
            providers=providers,
        )
        return [
            SearchResult(
                name=f"{r.given_name} {r.surname}",
                birth_date=r.birth_date.to_gedcom() if r.birth_date else None,
                death_date=r.death_date.to_gedcom() if r.death_date else None,
                birth_place=r.birth_place.name if r.birth_place else None,
                source_level=r.source_level.value,
                provider=r.provider,
                url=r.url,
            )
            for r in response.results
        ]

    @kernel_function(
        name="search_vital_records",
        description="Search specifically for vital records (birth, marriage, death)"
    )
    async def search_vital_records(
        self,
        surname: str,
        given_name: str,
        event_type: str,  # "birth", "marriage", "death"
        year_range: tuple[int, int],
        location: str,
    ) -> list[SearchResult]:
        """Search for specific vital records."""
        # Implementation
        pass
```

### Example Plugin: GEDCOM

```python
class GedcomPlugin:
    """GEDCOM file operations."""

    def __init__(self):
        self._manager = GedcomManager()

    @kernel_function(
        name="load_gedcom",
        description="Load a GEDCOM file"
    )
    def load_gedcom(self, file_path: str) -> dict:
        """Load GEDCOM file and return statistics."""
        self._manager.load(file_path)
        return self._manager.stats()

    @kernel_function(
        name="find_person",
        description="Find a person in the loaded GEDCOM"
    )
    def find_person(
        self,
        surname: str | None = None,
        given_name: str | None = None,
    ) -> list[dict]:
        """Find persons matching the criteria."""
        persons = self._manager.find_persons(
            surname=surname,
            given_name=given_name,
        )
        return [
            {
                "id": p.gedcom_id,
                "name": p.primary_name.full_name() if p.primary_name else "Unknown",
                "birth": p.birth.date.to_gedcom() if p.birth and p.birth.date else None,
                "death": p.death.date.to_gedcom() if p.death and p.death.date else None,
            }
            for p in persons
        ]

    @kernel_function(
        name="generate_surname_variants",
        description="Generate spelling variants for a surname"
    )
    def generate_surname_variants(self, surname: str) -> list[str]:
        """Generate surname spelling variants."""
        return self._manager.generate_surname_variants(surname)

    @kernel_function(
        name="validate_gedcom",
        description="Validate GEDCOM file integrity"
    )
    def validate_gedcom(self) -> list[str]:
        """Validate the loaded GEDCOM file."""
        return self._manager.validate()
```

### Example Plugin: GPS Validation

```python
class GPSValidationPlugin:
    """Genealogical Proof Standard validation."""

    def __init__(self):
        self._gps = GenealogyProofStandard()

    @kernel_function(
        name="validate_proof",
        description="Validate a proof summary against GPS standards"
    )
    def validate_proof(self, proof_summary: dict) -> dict:
        """Validate proof summary meets GPS requirements."""
        ps = ProofSummary(**proof_summary)
        result = self._gps.validate_proof(ps)
        return {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
        }

    @kernel_function(
        name="assess_confidence",
        description="Assess confidence level for a research case"
    )
    def assess_confidence(self, case: dict) -> str:
        """Assess confidence level based on evidence."""
        level = self._gps.assess_confidence(case)
        return level.name

    @kernel_function(
        name="correlate_evidence",
        description="Check if multiple pieces of evidence are consistent"
    )
    def correlate_evidence(self, evidence_list: list[dict]) -> dict:
        """Correlate multiple pieces of evidence."""
        result = self._gps.correlate_evidence(evidence_list)
        return {
            "is_consistent": result.is_consistent,
            "confidence": result.confidence.name,
            "conflicts": result.conflicts,
        }
```

---

## AutoGen Configuration

### Agent Setup

```python
# src/genealogy_assistant/agents/config.py

from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from semantic_kernel import Kernel

def create_genealogy_agents(kernel: Kernel, llm_config: dict):
    """Create the genealogy research agent team."""

    # Research Coordinator - primary agent
    coordinator = AssistantAgent(
        name="ResearchCoordinator",
        system_message=RESEARCH_COORDINATOR_PROMPT,
        llm_config=llm_config,
    )

    # Source Evaluator
    source_evaluator = AssistantAgent(
        name="SourceEvaluator",
        system_message=SOURCE_EVALUATOR_PROMPT,
        llm_config=llm_config,
    )

    # Conflict Resolver
    conflict_resolver = AssistantAgent(
        name="ConflictResolver",
        system_message=CONFLICT_RESOLVER_PROMPT,
        llm_config=llm_config,
    )

    # Report Writer
    report_writer = AssistantAgent(
        name="ReportWriter",
        system_message=REPORT_WRITER_PROMPT,
        llm_config=llm_config,
    )

    # DNA Analyst
    dna_analyst = AssistantAgent(
        name="DNAAnalyst",
        system_message=DNA_ANALYST_PROMPT,
        llm_config=llm_config,
    )

    # Paleographer
    paleographer = AssistantAgent(
        name="Paleographer",
        system_message=PALEOGRAPHER_PROMPT,
        llm_config=llm_config,
    )

    # Record Locator
    record_locator = AssistantAgent(
        name="RecordLocator",
        system_message=RECORD_LOCATOR_PROMPT,
        llm_config=llm_config,
    )

    # Archive Specialist
    archive_specialist = AssistantAgent(
        name="ArchiveSpecialist",
        system_message=ARCHIVE_SPECIALIST_PROMPT,
        llm_config=llm_config,
    )

    # User Proxy (for tool execution)
    user_proxy = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",  # or "TERMINATE" for interactive
        code_execution_config=False,
    )

    # Register SK plugins as tools
    register_sk_tools(coordinator, kernel)
    register_sk_tools(source_evaluator, kernel)
    register_sk_tools(record_locator, kernel)

    return {
        "coordinator": coordinator,
        "source_evaluator": source_evaluator,
        "conflict_resolver": conflict_resolver,
        "report_writer": report_writer,
        "dna_analyst": dna_analyst,
        "paleographer": paleographer,
        "record_locator": record_locator,
        "archive_specialist": archive_specialist,
        "user_proxy": user_proxy,
    }


def create_research_group_chat(agents: dict) -> GroupChat:
    """Create the multi-agent group chat."""

    all_agents = [
        agents["user_proxy"],
        agents["coordinator"],
        agents["source_evaluator"],
        agents["conflict_resolver"],
        agents["report_writer"],
        agents["dna_analyst"],
        agents["paleographer"],
        agents["record_locator"],
        agents["archive_specialist"],
    ]

    group_chat = GroupChat(
        agents=all_agents,
        messages=[],
        max_round=20,
        speaker_selection_method="auto",  # Let LLM decide who speaks
    )

    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=agents["coordinator"].llm_config,
    )

    return group_chat, manager
```

### LLM Configuration

```python
# src/genealogy_assistant/agents/llm_config.py

def get_llm_config(provider: str = "anthropic") -> dict:
    """Get LLM configuration for AutoGen."""

    configs = {
        "anthropic": {
            "config_list": [{
                "model": "claude-sonnet-4-20250514",
                "api_key": os.environ.get("ANTHROPIC_API_KEY"),
                "api_type": "anthropic",
            }],
            "temperature": 0.3,
        },
        "openai": {
            "config_list": [{
                "model": "gpt-4-turbo",
                "api_key": os.environ.get("OPENAI_API_KEY"),
            }],
            "temperature": 0.3,
        },
        "azure": {
            "config_list": [{
                "model": "gpt-4",
                "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
                "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT"),
                "api_type": "azure",
                "api_version": "2024-02-15-preview",
            }],
            "temperature": 0.3,
        },
        "ollama": {
            "config_list": [{
                "model": "llama3:70b",
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",  # Ollama doesn't need real key
            }],
            "temperature": 0.3,
        },
    }

    return configs.get(provider, configs["anthropic"])
```

---

## Semantic Kernel Setup

```python
# src/genealogy_assistant/kernel/setup.py

import semantic_kernel as sk
from semantic_kernel.connectors.ai.anthropic import AnthropicChatCompletion
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, AzureChatCompletion
from semantic_kernel.memory import SemanticTextMemory
from semantic_kernel.connectors.memory.chroma import ChromaMemoryStore

async def create_kernel(
    llm_provider: str = "anthropic",
    enable_memory: bool = True,
) -> sk.Kernel:
    """Create and configure Semantic Kernel."""

    kernel = sk.Kernel()

    # Add LLM service based on provider
    if llm_provider == "anthropic":
        kernel.add_service(AnthropicChatCompletion(
            service_id="chat",
            ai_model_id="claude-sonnet-4-20250514",
        ))
    elif llm_provider == "openai":
        kernel.add_service(OpenAIChatCompletion(
            service_id="chat",
            ai_model_id="gpt-4-turbo",
        ))
    elif llm_provider == "azure":
        kernel.add_service(AzureChatCompletion(
            service_id="chat",
            deployment_name="gpt-4",
        ))

    # Add plugins
    kernel.add_plugin(UnifiedSearchPlugin(), plugin_name="search")
    kernel.add_plugin(GedcomPlugin(), plugin_name="gedcom")
    kernel.add_plugin(GPSValidationPlugin(), plugin_name="gps")
    kernel.add_plugin(ProofSummaryPlugin(), plugin_name="reports")
    kernel.add_plugin(CitationsPlugin(), plugin_name="citations")

    # Add memory if enabled
    if enable_memory:
        memory_store = ChromaMemoryStore(persist_directory="./genealogy_memory")
        memory = SemanticTextMemory(storage=memory_store, embeddings_generator=kernel)
        kernel.add_plugin(TextMemoryPlugin(memory), plugin_name="memory")

    return kernel
```

---

## Memory / RAG Layer

### Research Memory Plugin

```python
# src/genealogy_assistant/plugins/memory/research_memory_plugin.py

class ResearchMemoryPlugin:
    """Persistent memory for genealogy research."""

    def __init__(self, memory: SemanticTextMemory):
        self._memory = memory
        self._collections = {
            "persons": "genealogy_persons",
            "sources": "genealogy_sources",
            "research_logs": "genealogy_research_logs",
            "conclusions": "genealogy_conclusions",
        }

    @kernel_function(
        name="remember_person",
        description="Store information about a person for later retrieval"
    )
    async def remember_person(
        self,
        person_id: str,
        name: str,
        facts: str,
        sources: str,
    ) -> str:
        """Store person information in memory."""
        await self._memory.save_information(
            collection=self._collections["persons"],
            id=person_id,
            text=f"Person: {name}\nFacts: {facts}\nSources: {sources}",
        )
        return f"Remembered {name}"

    @kernel_function(
        name="recall_person",
        description="Retrieve information about a person"
    )
    async def recall_person(self, query: str, limit: int = 5) -> list[str]:
        """Retrieve person information from memory."""
        results = await self._memory.search(
            collection=self._collections["persons"],
            query=query,
            limit=limit,
        )
        return [r.text for r in results]

    @kernel_function(
        name="remember_research",
        description="Store research findings for a research question"
    )
    async def remember_research(
        self,
        question: str,
        findings: str,
        confidence: str,
        next_steps: str,
    ) -> str:
        """Store research findings in memory."""
        await self._memory.save_information(
            collection=self._collections["research_logs"],
            id=str(uuid4()),
            text=f"Question: {question}\nFindings: {findings}\nConfidence: {confidence}\nNext: {next_steps}",
        )
        return "Research logged"

    @kernel_function(
        name="recall_related_research",
        description="Find previous research related to a query"
    )
    async def recall_related_research(self, query: str, limit: int = 5) -> list[str]:
        """Find related previous research."""
        results = await self._memory.search(
            collection=self._collections["research_logs"],
            query=query,
            limit=limit,
        )
        return [r.text for r in results]
```

---

## Directory Structure

```
src/genealogy_assistant/
├── __init__.py
├── agents/                      # NEW: AutoGen agents
│   ├── __init__.py
│   ├── config.py               # Agent creation and setup
│   ├── llm_config.py           # LLM provider configuration
│   ├── prompts.py              # Agent system prompts
│   └── tools.py                # Tool registration helpers
├── kernel/                      # NEW: Semantic Kernel setup
│   ├── __init__.py
│   ├── setup.py                # Kernel initialization
│   └── memory.py               # Memory configuration
├── plugins/                     # NEW: SK plugins (refactored from existing)
│   ├── __init__.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── familysearch_plugin.py
│   │   ├── geneanet_plugin.py
│   │   ├── findagrave_plugin.py
│   │   ├── belgian_archives_plugin.py
│   │   └── unified_search_plugin.py
│   ├── gedcom/
│   │   ├── __init__.py
│   │   └── gedcom_plugin.py
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── proof_summary_plugin.py
│   │   ├── pedigree_plugin.py
│   │   ├── family_group_plugin.py
│   │   └── citations_plugin.py
│   ├── gps/
│   │   ├── __init__.py
│   │   └── validation_plugin.py
│   └── memory/
│       ├── __init__.py
│       └── research_memory_plugin.py
├── core/                        # EXISTING: Keep as-is
│   ├── models.py
│   ├── gps.py
│   └── gedcom.py
├── search/                      # EXISTING: Keep, wrap in plugins
│   ├── base.py
│   ├── familysearch.py
│   ├── geneanet.py
│   └── unified.py
├── reports/                     # EXISTING: Keep, wrap in plugins
│   ├── proof.py
│   ├── pedigree.py
│   └── citations.py
├── api/
│   ├── __init__.py
│   └── assistant.py            # REFACTOR: Use new agent system
├── cli.py                       # UPDATE: Add agent commands
└── web.py                       # UPDATE: Add agent endpoints
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Add dependencies: `semantic-kernel`, `pyautogen`, `chromadb`
2. Create `kernel/setup.py` with basic SK initialization
3. Create `agents/llm_config.py` with provider configs
4. Create `agents/prompts.py` with all agent prompts

### Phase 2: Plugins (Week 2)
1. Create `plugins/search/unified_search_plugin.py` wrapping existing search
2. Create `plugins/gedcom/gedcom_plugin.py` wrapping GedcomManager
3. Create `plugins/gps/validation_plugin.py` wrapping GPS validator
4. Create `plugins/reports/` wrapping report generators

### Phase 3: Agents (Week 3)
1. Create `agents/config.py` with agent definitions
2. Implement `register_sk_tools()` to connect SK plugins to AutoGen
3. Create GroupChat configuration
4. Test individual agents with plugins

### Phase 4: Integration (Week 4)
1. Refactor `api/assistant.py` to use new agent system
2. Update CLI with `--agent` commands
3. Add memory persistence with ChromaDB
4. End-to-end testing

### Phase 5: Polish (Week 5)
1. Add streaming responses
2. Implement conversation history management
3. Add monitoring/logging
4. Documentation and examples

---

## Dependencies

```toml
# pyproject.toml additions

[project.dependencies]
semantic-kernel = ">=1.0.0"
pyautogen = ">=0.2.0"
chromadb = ">=0.4.0"

[project.optional-dependencies]
anthropic = ["anthropic>=0.18.0"]
openai = ["openai>=1.0.0"]
azure = ["azure-identity>=1.15.0"]
ollama = ["ollama>=0.1.0"]
```

---

## Configuration

```yaml
# config/agents.yaml

llm:
  provider: anthropic  # anthropic, openai, azure, ollama
  model: claude-sonnet-4-20250514
  temperature: 0.3
  max_tokens: 4096

memory:
  enabled: true
  provider: chroma
  persist_directory: ./genealogy_memory

agents:
  max_rounds: 20
  speaker_selection: auto  # auto, round_robin, random

plugins:
  search:
    providers:
      - familysearch
      - geneanet
      - findagrave
    rate_limit: 1.0  # seconds between requests

  gedcom:
    default_path: ./data/family.ged
```

---

## Usage Example

```python
from genealogy_assistant.kernel.setup import create_kernel
from genealogy_assistant.agents.config import create_genealogy_agents, create_research_group_chat
from genealogy_assistant.agents.llm_config import get_llm_config

async def research_ancestor():
    # Initialize Semantic Kernel
    kernel = await create_kernel(llm_provider="anthropic")

    # Create agents
    llm_config = get_llm_config("anthropic")
    agents = create_genealogy_agents(kernel, llm_config)

    # Create group chat
    group_chat, manager = create_research_group_chat(agents)

    # Start research
    await agents["user_proxy"].initiate_chat(
        manager,
        message="""
        Research question: Who were the parents of Jean Joseph Herinckx,
        born approximately 1895 in Tervuren, Belgium?

        Known facts:
        - Emigrated to Detroit, Michigan around 1920
        - Married Marie Catherine De Smet
        - Had children Victor and Frank

        Please conduct GPS-compliant research.
        """
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(research_ancestor())
```

---

## Success Criteria

1. **LLM Flexibility**: Can switch between Claude/GPT-4/Ollama via config change
2. **Multi-Agent**: Agents collaborate on complex research questions
3. **Plugin System**: Existing search/GEDCOM/report code works as SK plugins
4. **Memory**: Research findings persist across sessions
5. **GPS Compliance**: All outputs follow Genealogical Proof Standard
6. **Tests Pass**: Existing 199 tests continue to pass
