# Agentic AI Architecture Design

**Date:** 2026-01-17
**Status:** Draft - Pending Review
**Authors:** Thomas Vincent, Claude Opus 4.5

---

## Executive Summary

This document describes a multi-agent AI research platform for genealogical research that produces conclusions meeting the Genealogical Proof Standard (GPS). The system emphasizes accuracy, explainability, auditability, and long-term research integrity over speed or convenience.

### Core Design Principles

1. **Accuracy over convenience** - Never sacrifice correctness for speed
2. **Immutable facts, never silent edits** - All changes create new versions
3. **Critics advise; Workflow decides** - Clear separation of powers
4. **Evidence, provenance, and uncertainty are first-class** - Everything is tracked
5. **Write-optimized ledger + read-optimized projections (CQRS)** - Right tool for each job

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Agent Control Plane](#2-agent-control-plane)
3. [Agent Specifications](#3-agent-specifications)
4. [Agent Communication Protocol](#4-agent-communication-protocol)
5. [Canonical Fact Ledger](#5-canonical-fact-ledger)
6. [Read-Side Projections](#6-read-side-projections)
7. [User Interfaces](#7-user-interfaces)
8. [Tool Layer](#8-tool-layer)
9. [GPS Enforcement](#9-gps-enforcement)
10. [Implementation Decisions](#10-implementation-decisions)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                              │
│  ┌──────────┐ ┌───────────┐ ┌─────────┐ ┌────────────────────┐      │
│  │   Chat   │ │ Dashboard │ │  Queue  │ │ Gramps Integration │      │
│  └────┬─────┘ └─────┬─────┘ └────┬────┘ └─────────┬──────────┘      │
└───────┼─────────────┼────────────┼────────────────┼─────────────────┘
        │             │            │                │
        └─────────────┴─────┬──────┴────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AGENT CONTROL PLANE                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                 GPS CRITIC AGENTS (Parallel)                 │    │
│  │   ┌─────────────────────┐  ┌─────────────────────┐          │    │
│  │   │  Standards Critic   │  │  Reasoning Critic   │          │    │
│  │   │  (Pillars 1,2,5)    │  │  (Pillars 3,4)      │          │    │
│  │   └─────────────────────┘  └─────────────────────┘          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         ▲               ▲                ▲              ▲            │
│         │               │                │              │            │
│  ┌──────┴──────┐ ┌──────┴─────┐ ┌───────┴──────┐ ┌─────┴──────┐    │
│  │  Research   │◄─►  Data     │◄─► Recommend-  │◄─► Workflow  │    │
│  │  Agent      │ │  Quality   │ │  ation Agent │ │  Agent     │    │
│  └──────┬──────┘ │  Agent     │ └───────┬──────┘ └─────┬──────┘    │
│         │        └──────┬─────┘         │              │            │
│         ▼               ▼               ▼              ▼            │
│  ┌──────────────┐ ┌───────────┐ ┌──────────────┐ ┌────────────┐    │
│  │  Citation    │◄─►Translation◄─► Ethnicity/  │ │ Synthesis  │    │
│  │  Agent       │ │  Agent    │ │  DNA Agent   │ │ Agent      │    │
│  └──────────────┘ └───────────┘ └──────────────┘ └────────────┘    │
│                                                                      │
│  ◄─► = Collaborative mesh (agents communicate directly)             │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TOOL LAYER                                   │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────────┐   │
│  │FamilySearch│ │ Ancestry │ │  Archives │ │ Web Scraping       │   │
│  │    API     │ │   API    │ │   APIs    │ │ (FindAGrave, etc.) │   │
│  └────────────┘ └──────────┘ └───────────┘ └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (CQRS)                               │
│                                                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐     │
│  │   CANONICAL FACT LEDGER │    │     READ-SIDE PROJECTIONS   │     │
│  │       (RocksDB)         │───►│  ┌─────────┐ ┌───────────┐  │     │
│  │                         │    │  │ DuckDB  │ │  Search   │  │     │
│  │  • Immutable            │    │  │ (SQL)   │ │  Index    │  │     │
│  │  • Append-only          │    │  └─────────┘ └───────────┘  │     │
│  │  • Versioned            │    │  ┌─────────────────────┐    │     │
│  │  • Full provenance      │    │  │   Gramps Sync       │    │     │
│  └─────────────────────────┘    │  └─────────────────────┘    │     │
│                                 └─────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### Autonomy Model

**Semi-Autonomous**: Agents perform research and prepare recommendations. GPS Critics validate in parallel, attaching confidence scores and compliance notes. The user approves before any changes are committed to the tree.

---

## 2. Agent Control Plane

### Model Strategy

| Agent | Model | Reasoning |
|-------|-------|-----------|
| Research Agent | Claude Opus | Complex reasoning, following leads, connecting evidence |
| GPS Standards Critic | Claude Opus | Nuanced judgment, standards compliance |
| GPS Reasoning Critic | Claude Opus | Logic validation, conflict resolution |
| Workflow Agent | Claude Sonnet | Orchestration, task decomposition |
| Recommendation Agent | Claude Sonnet | Pattern matching, gap analysis |
| Data Quality Agent | Claude Haiku | Fast validation, rule-based checks |
| Citation Agent | Claude Sonnet | Formatting, Evidence Explained standards |
| Translation Agent | GPT-4o | Strong multilingual (French/Dutch/German/Latin) |
| Ethnicity/DNA Agent | Claude Opus | Specialized knowledge, sensitive handling |
| Synthesis Agent | Claude Sonnet | Narrative generation, proof summaries |

**Cost optimization**: Haiku for high-volume checks, Opus only for deep reasoning.

### Governance Model

- **Facts are proposed, never asserted** - All findings start as proposals
- **Critics cannot mutate or veto** - They advise only
- **Workflow Agent applies recommendations** - Single authority to ledger
- **All uncertainty is explicit** - No hidden confidence
- **Conflicting evidence may coexist if labeled** - Reality is messy

---

## 3. Agent Specifications

### 3.1 Workflow Agent

```yaml
agent: workflow_agent
model: claude-sonnet
role: "Manage full lifecycle of genealogical research tasks"

authority:
  - ONLY agent allowed to write to Fact Ledger
  - ONLY agent allowed to apply confidence deltas
  - ONLY agent allowed to set final Fact status

responsibilities:
  - Spawn and coordinate agents
  - Retry failed tasks (max 2 retries)
  - Handle tool failures using fallback rules
  - Resolve conflicts using critic recommendations
  - Issue Search Revision Requests when confidence < 0.7
  - Decide when a task is complete

must_output:
  - status_change_reason: "Required explanation for every status change"
  - task_completion_summary: "What was accomplished"
  - next_steps: "Remaining work if any"

must_not:
  - Discover new evidence
  - Perform analysis itself
  - Override critic feedback without justification
```

### 3.2 GPS Standards Critic

```yaml
agent: gps_standards_critic
model: claude-opus
role: "Evaluate findings against GPS Pillars 1, 2, and 5"

responsibilities:
  - Pillar 1: Reasonably exhaustive research
  - Pillar 2: Complete and accurate citations
  - Pillar 5: Soundly written conclusions

must_output:
  - citation_quality_score: 0-100
  - exhaustiveness_assessment: "sufficient" | "incomplete" | "minimal"
  - missing_repositories: ["list of unsearched sources"]
  - citation_errors: ["formatting issues, missing fields"]
  - suggested_confidence_delta: -20 to +10

must_not:
  - Introduce new evidence
  - Query external sources
  - Override Reasoning Critic
  - Force accept/reject decisions
```

### 3.3 GPS Reasoning Critic

```yaml
agent: gps_reasoning_critic
model: claude-opus
role: "Evaluate findings against GPS Pillars 3 and 4"

responsibilities:
  - Pillar 3: Analysis and correlation
  - Pillar 4: Resolution of conflicting evidence

must_evaluate:
  - Informant reliability weighting
  - Logical fallacy detection (Same Name/Different Man, Ancestor by Assumption)
  - Unresolved conflict identification
  - Evidence weight comparisons

must_output:
  - logical_fallacies: ["detected fallacies with explanations"]
  - conflict_status: "none" | "unresolved" | "resolved_in_favor_of"
  - informant_reliability: "primary" | "secondary" | "hearsay"
  - evidence_weight_explanation: "narrative reasoning"
  - suggested_confidence_delta: -30 to +10

must_not:
  - Introduce new evidence
  - Rewrite conclusions
  - Enforce acceptance or rejection
```

### 3.4 Research Agent

```yaml
agent: research_agent
model: claude-opus
role: "Discover records, follow leads, propose candidate facts"

responsibilities:
  - Query external sources via Tool Layer
  - Follow citation trails (record A mentions record B)
  - Extract facts from retrieved documents
  - Propose facts with initial confidence estimate

must_output:
  - proposed_facts: [{fact, source, extraction_confidence}]
  - search_log: ["repository searched", "query used", "results found/not found"]
  - leads_to_follow: ["potential next searches"]
  - provenance: {tool_used, api_response_id, timestamp}

must_not:
  - Write to ledger
  - Assess GPS compliance (that's Critics' job)
  - Skip negative results (must log "not found")
```

### 3.5 Data Quality Agent

```yaml
agent: data_quality_agent
model: claude-haiku
role: "Fast validation and consistency checks"

responsibilities:
  - Detect impossible dates (death before birth, etc.)
  - Flag duplicate persons
  - Identify missing required fields
  - Check referential integrity (family links exist)

must_output:
  - validation_errors: [{type, severity, affected_facts}]
  - duplicate_candidates: [{person_a, person_b, similarity_score}]
  - integrity_issues: ["orphan family references", etc.]

triggers:
  - On every PROPOSED_FACT (fast pre-check)
  - Periodic full-tree scan (background)
```

### 3.6 Translation Agent

```yaml
agent: translation_agent
model: gpt-4o
role: "Translate foreign records preserving ambiguity"

responsibilities:
  - Translate French, Dutch, German, Latin documents
  - Preserve original text alongside translation
  - Flag uncertain translations explicitly
  - Handle archaic spellings and abbreviations

must_output:
  - original_text: "string"
  - translated_text: "string"
  - uncertain_terms: [{original, possible_meanings: []}]
  - language_detected: "fr" | "nl" | "de" | "la"

must_not:
  - Guess at unclear terms (mark as uncertain)
  - Discard original text
```

### 3.7 Citation Agent

```yaml
agent: citation_agent
model: claude-sonnet
role: "Format accepted facts using Evidence Explained standards"

responsibilities:
  - Apply Evidence Explained citation templates
  - Categorize source level (primary/secondary/tertiary)
  - Generate bibliography entries
  - Validate citation completeness

must_output:
  - formatted_citation: "string"
  - source_level: "primary" | "secondary" | "tertiary"
  - template_used: "Civil Registration" | "Census" | etc.
  - missing_fields: ["repository address", etc.]

triggers:
  - After ACCEPTED_FACT from Workflow Agent
```

### 3.8 Ethnicity/DNA Agent

```yaml
agent: ethnicity_dna_agent
model: claude-opus
role: "Probabilistic interpretation with strict uncertainty labeling"

responsibilities:
  - Interpret DNA match data
  - Navigate ethnic-specific records (Dawes Rolls, Freedmen's Bureau, etc.)
  - Handle sensitive designations appropriately
  - Provide probability ranges, not certainties

must_output:
  - interpretation: "narrative"
  - confidence_range: {low: 0.0, high: 1.0}
  - caveats: ["DNA alone cannot prove tribal membership", etc.]
  - relevant_records: ["record collections to search"]

must_not:
  - Assert ethnic identity without documentary evidence
  - Provide single-point confidence (always ranges)
```

### 3.9 Recommendation Agent

```yaml
agent: recommendation_agent
model: claude-sonnet
role: "Identify gaps and suggest next research steps"

responsibilities:
  - Analyze tree for missing information
  - Prioritize research opportunities
  - Suggest specific repositories and record sets
  - Track research progress

must_output:
  - recommendations: [{priority, person_id, gap_type, suggested_sources}]
  - research_roadmap: "ordered list of next steps"
  - quick_wins: "low-effort high-value opportunities"

triggers:
  - After ACCEPTED_FACT (update recommendations)
  - On user request
  - Periodic background analysis
```

### 3.10 Synthesis Agent

```yaml
agent: synthesis_agent
model: claude-sonnet
role: "Produce narratives and proof summaries from accepted facts ONLY"

responsibilities:
  - Generate proof summaries following GPS format
  - Write family narratives
  - Summarize open research questions
  - Create research reports

must_output:
  - narrative: "markdown"
  - facts_used: [fact_ids]  # Must reference only ACCEPTED facts
  - open_questions: ["unresolved items"]
  - gps_compliance_statement: "how this meets GPS"

must_not:
  - Reference PROPOSED or REJECTED facts
  - Introduce conclusions not in ledger
  - Speculate beyond evidence
```

---

## 4. Agent Communication Protocol

### Message Envelope

```json
{
  "message_id": "uuid",
  "timestamp": "iso8601",
  "source_agent": "research_agent",
  "target_agents": ["gps_standards_critic", "gps_reasoning_critic"],
  "message_type": "PROPOSED_FACT",
  "correlation_id": "uuid",
  "payload": { }
}
```

### Message Types

| Type | From | To | Purpose |
|------|------|----|---------|
| `TASK` | Workflow | Any Agent | Assign work |
| `PROPOSED_FACT` | Research/Translation/DNA | Critics + Workflow | New finding, needs review |
| `CRITIQUE` | Critics | Workflow | GPS assessment + confidence score |
| `ACCEPTED_FACT` | Workflow | Ledger + Projections | Approved for commit |
| `SEARCH_REVISION_REQUEST` | Critics/Workflow | Research | Below threshold, needs more evidence |
| `CONFLICT_DETECTED` | Data Quality | Workflow | Conflicting facts found |
| `TRANSLATION_REQUEST` | Research | Translation | Foreign document encountered |
| `CITATION_REQUEST` | Workflow | Citation | Format accepted fact |
| `SYNTHESIS_REQUEST` | User/Workflow | Synthesis | Generate narrative |

### Example Flow: Research to Acceptance

```
User Request: "Find Jean Herinckx's parents"
                            │
                            ▼
                    ┌───────────────┐
                    │ Workflow Agent │
                    └───────┬───────┘
                            │ TASK
                            ▼
                    ┌───────────────┐
                    │ Research Agent │
                    └───────┬───────┘
                            │ (queries FamilySearch, Belgian Archives)
                            │
                            ▼ PROPOSED_FACT
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌───────────────────┐                 ┌───────────────────┐
│ Standards Critic  │                 │ Reasoning Critic  │
│ (parallel review) │                 │ (parallel review) │
└─────────┬─────────┘                 └─────────┬─────────┘
          │                                     │
          └──────────CRITIQUE───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Workflow Agent │
                    │ (evaluate)     │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ACCEPTED_FACT    SEARCH_REVISION    CONFLICT_HOLD
    (confidence ≥0.7) (confidence <0.7)  (unresolved)
          │                 │                 │
          ▼                 ▼                 ▼
    Write to Ledger   Back to Research   Queue for User
          │
          ▼
    Update Projections
          │
          ▼
    Citation Agent (format)
          │
          ▼
    Notify User (via Queue)
```

### Combined Critique Output

```json
{
  "fact_id": "uuid",
  "proposed_by": "research_agent",
  "critiques": {
    "standards": {
      "citation_score": 85,
      "exhaustiveness": "incomplete",
      "missing_repos": ["Belgian State Archives - marriage records"],
      "confidence_delta": -10
    },
    "reasoning": {
      "fallacies": [],
      "conflict_status": "none",
      "informant_reliability": "primary",
      "confidence_delta": 0
    }
  },
  "combined_confidence": 0.75,
  "recommendation": "ACCEPT_WITH_NOTES"
}
```

---

## 5. Canonical Fact Ledger

### Technology Choice: RocksDB

- Embedded key-value store (no server)
- Optimized for write-heavy workloads
- Supports atomic batches
- Battle-tested (used by Facebook, Netflix, Uber)

### Fact Record Structure

```python
@dataclass
class Fact:
    """Immutable fact record in the ledger."""

    # Identity
    fact_id: UUID                    # Stable across versions
    version: int                     # Increments on each change
    supersedes: UUID | None          # Previous version's record_id
    record_id: UUID                  # Unique per version (fact_id + version)

    # Content
    fact_type: FactType              # BIRTH, DEATH, MARRIAGE, etc.
    subject_person_id: UUID          # Who this fact is about
    content: dict                    # Fact-specific data

    # Provenance
    source_citations: list[Citation] # Evidence Explained formatted
    proposed_by: str                 # Agent that discovered this
    extraction_method: str           # "api:familysearch" | "ocr:document"
    original_document_ref: str | None

    # Confidence & Status
    initial_confidence: float        # 0.0 - 1.0
    confidence_deltas: list[ConfidenceDelta]
    final_confidence: float          # Computed
    status: FactStatus               # PROPOSED | ACCEPTED | etc.

    # Audit
    created_at: datetime
    status_changed_at: datetime
    status_change_reason: str        # Required from Workflow Agent

    # Relationships
    corroborates: list[UUID]         # Other facts this supports
    conflicts_with: list[UUID]       # Unresolved conflicts
    conflict_resolution: str | None
```

### Supporting Types

```python
class FactType(Enum):
    BIRTH = "birth"
    DEATH = "death"
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    RESIDENCE = "residence"
    OCCUPATION = "occupation"
    IMMIGRATION = "immigration"
    NATURALIZATION = "naturalization"
    MILITARY_SERVICE = "military_service"
    ENROLLMENT = "enrollment"        # Tribal rolls
    NAME_VARIANT = "name_variant"
    RELATIONSHIP = "relationship"    # Parent-child, spouse

class FactStatus(Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    NEEDS_REVISION = "needs_revision"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

@dataclass
class ConfidenceDelta:
    """Audit trail of confidence adjustments."""
    applied_by: str
    delta: float                     # -0.3 to +0.1
    reason: str
    timestamp: datetime

@dataclass
class Citation:
    """Evidence Explained formatted citation."""
    citation_id: UUID
    formatted_full: str
    formatted_short: str
    formatted_bibliography: str
    source_level: SourceLevel        # PRIMARY | SECONDARY | TERTIARY
    repository: str
    access_date: date
    original_text: str | None        # For translated documents
```

### Ledger Operations

```python
class FactLedger:
    """Append-only fact storage. Only Workflow Agent may write."""

    def propose_fact(self, fact: Fact) -> UUID:
        """Research Agent proposes, status=PROPOSED."""

    def update_status(
        self,
        fact_id: UUID,
        new_status: FactStatus,
        reason: str,
        deltas: list[ConfidenceDelta]
    ) -> UUID:
        """Creates new version. Returns new record_id."""

    def get_current_version(self, fact_id: UUID) -> Fact:
        """Returns latest version."""

    def get_history(self, fact_id: UUID) -> list[Fact]:
        """Returns all versions, oldest first."""

    def get_accepted_facts(self, person_id: UUID) -> list[Fact]:
        """Returns only ACCEPTED facts for a person."""

    # NO delete operation - facts are rejected, never removed
```

### Immutability Guarantees

1. **No updates** - Every change creates a new version
2. **No deletes** - Facts are marked REJECTED, never removed
3. **Full history** - Every version preserved forever
4. **Provenance chain** - `supersedes` links form complete audit trail
5. **Deterministic replay** - Can rebuild any point-in-time state

---

## 6. Read-Side Projections

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FACT LEDGER (RocksDB)                        │
│                    [Immutable Source of Truth]                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼ Event Stream
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  SQL Store    │   │ Search Index  │   │ Gramps Sync   │
│  (DuckDB)     │   │ (Tantivy/     │   │               │
│               │   │  Meilisearch) │   │ • ACCEPTED    │
│ • Person view │   │               │   │   facts only  │
│ • Family view │   │ • Full-text   │   │ • Auto-sync   │
│ • Timeline    │   │ • Fuzzy name  │   │               │
│ • Statistics  │   │ • Geo search  │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
```

### SQL Schema (DuckDB)

```sql
-- Materialized from ACCEPTED facts only
CREATE TABLE persons (
    person_id UUID PRIMARY KEY,
    display_name TEXT,
    birth_date DATE,
    birth_place TEXT,
    death_date DATE,
    death_place TEXT,
    confidence_score FLOAT,
    fact_count INT,
    last_updated TIMESTAMP
);

CREATE TABLE families (
    family_id UUID PRIMARY KEY,
    husband_id UUID REFERENCES persons,
    wife_id UUID REFERENCES persons,
    marriage_date DATE,
    marriage_place TEXT,
    divorce_date DATE
);

CREATE TABLE family_children (
    family_id UUID REFERENCES families,
    child_id UUID REFERENCES persons,
    birth_order INT
);

CREATE TABLE fact_summary (
    fact_id UUID PRIMARY KEY,
    person_id UUID REFERENCES persons,
    fact_type TEXT,
    date DATE,
    place TEXT,
    confidence FLOAT,
    source_level TEXT,
    citation_short TEXT
);

CREATE TABLE research_queue (
    item_id UUID PRIMARY KEY,
    person_id UUID REFERENCES persons,
    task_type TEXT,
    status TEXT,
    assigned_agent TEXT,
    created_at TIMESTAMP,
    findings_count INT
);

CREATE TABLE gps_scores (
    person_id UUID REFERENCES persons,
    pillar_1_exhaustive FLOAT,
    pillar_2_citations FLOAT,
    pillar_3_analysis FLOAT,
    pillar_4_conflicts FLOAT,
    pillar_5_conclusion FLOAT,
    overall_score FLOAT,
    last_assessed TIMESTAMP
);
```

### Projection Rebuild

```python
class ProjectionBuilder:
    """Rebuilds projections from ledger."""

    def rebuild_all(self):
        """Nuclear option - replay entire ledger."""
        self.sql_store.truncate_all()
        self.search_index.clear()

        for fact in self.ledger.stream_all_accepted():
            self._apply_to_projections(fact)

    def rebuild_person(self, person_id: UUID):
        """Rebuild single person's projections."""
        facts = self.ledger.get_accepted_facts(person_id)
        self.sql_store.rebuild_person(person_id, facts)
        self.search_index.reindex_person(person_id, facts)

    def on_fact_accepted(self, fact: Fact):
        """Incremental update on new acceptance."""
        self._apply_to_projections(fact)
```

---

## 7. User Interfaces

### 7.1 Chat Interface

Conversational interaction with the agent system.

```
User: Find Jean Herinckx's parents

System: Starting research task for Jean Herinckx...

        [Research Agent] Searching FamilySearch...
        [Research Agent] Found birth record: Tervuren, 1850
        [Research Agent] Searching Belgian State Archives...

        [GPS Standards Critic] Citation score: 85/100
        [GPS Reasoning Critic] No logical fallacies detected

        [Workflow Agent] PROPOSED_FACT accepted (confidence: 0.78)

        Finding: Jean Joseph Herinckx
        Born: 15 March 1850, Tervuren, Belgium
        Father: Pierre Herinckx (proposed, awaiting your approval)
        Mother: Marie Janssens (proposed, awaiting your approval)

        [Approve] [Request More Evidence] [Reject]
```

### 7.2 Dashboard

Visual overview of research status.

```
┌─────────────────────────────────────────────────────────────┐
│  GENEALOGY RESEARCH DASHBOARD                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  AGENTS STATUS                    GPS COMPLIANCE             │
│  ┌─────────────────────┐         ┌────────────────────┐     │
│  │ Research    ● Active │         │ Overall: 78%       │     │
│  │ Critics     ● Active │         │ ████████░░ 78/100  │     │
│  │ Data Quality ○ Idle  │         │                    │     │
│  │ Translation  ○ Idle  │         │ Pillar 1: 85%      │     │
│  └─────────────────────┘         │ Pillar 2: 72%      │     │
│                                   │ Pillar 3: 80%      │     │
│  PENDING APPROVAL (3)             │ Pillar 4: 75%      │     │
│  ┌─────────────────────────────┐  │ Pillar 5: 78%      │     │
│  │ ◉ Jean Herinckx - parents  │  └────────────────────┘     │
│  │   Confidence: 0.78          │                             │
│  │ ◉ Marie Janssens - birth   │  RECENT ACTIVITY            │
│  │   Confidence: 0.72          │  • Birth record found       │
│  │ ◉ Pierre Herinckx - death  │  • 2 critiques completed    │
│  │   Confidence: 0.65          │  • 1 conflict detected      │
│  └─────────────────────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Approval Queue

Review and approve/reject findings.

```
┌─────────────────────────────────────────────────────────────┐
│  APPROVAL QUEUE                                    Filter ▼  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ PROPOSED FACT #1                                        ││
│  │ Subject: Jean Joseph Herinckx                           ││
│  │ Fact: Birth - 15 March 1850, Tervuren, Belgium          ││
│  │                                                         ││
│  │ CONFIDENCE: 0.78 ████████░░                             ││
│  │                                                         ││
│  │ GPS CRITIQUE:                                           ││
│  │ ┌─────────────────────────────────────────────────────┐ ││
│  │ │ Standards: Citation score 85/100                    │ ││
│  │ │ - Missing: Repository call number                   │ ││
│  │ │ Reasoning: No fallacies detected                    │ ││
│  │ │ - Primary informant (civil registrar)               │ ││
│  │ └─────────────────────────────────────────────────────┘ ││
│  │                                                         ││
│  │ EVIDENCE:                                               ││
│  │ • Belgian State Archives, Civil Registration            ││
│  │   Tervuren, Births 1850, Entry 45                       ││
│  │   [View Document]                                       ││
│  │                                                         ││
│  │ [✓ Approve] [↻ Request Revision] [✗ Reject]            ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 Gramps Integration

Findings appear as suggested entries in Gramps.

- Only ACCEPTED facts sync to Gramps
- Bidirectional: Gramps edits create new PROPOSED facts
- Conflict detection between local and agent findings
- Visual indicator for AI-discovered vs manual entries

---

## 8. Tool Layer

### Supported Integrations

| Tool | Type | Purpose |
|------|------|---------|
| FamilySearch API | Official API | Indexed records, trees |
| Ancestry API | Official API | Indexed records, DNA |
| FindMyPast API | Official API | UK/Ireland records |
| MyHeritage API | Official API | Records, DNA |
| Belgian State Archives | Web Scraping | Civil registration |
| FindAGrave | Web Scraping | Cemetery records |
| Newspapers.com | API + Scraping | Historical newspapers |
| Google Translate | API | Fallback translation |

### Tool Output Requirements

Every tool response must include:

```python
@dataclass
class ToolResponse:
    """Standardized tool output."""
    tool_name: str
    query: dict
    timestamp: datetime

    # Result
    success: bool
    records_found: int
    data: list[dict]

    # Provenance (required)
    api_response_id: str | None
    url_accessed: str
    raw_response_hash: str      # For verification

    # Reliability
    source_level: SourceLevel
    data_freshness: str         # "live" | "cached" | "stale"

    # Errors
    error_type: str | None
    error_message: str | None
    partial_results: bool       # True if some data retrieved
```

### Failure Handling

- Tool failures result in `INCOMPLETE` facts, never dropped data
- Retry with exponential backoff (max 3 attempts)
- Fallback to alternative sources if primary fails
- All failures logged for audit

---

## 9. GPS Enforcement

### The Five Pillars

Every conclusion is evaluated against all GPS pillars:

| Pillar | Requirement | Enforced By |
|--------|-------------|-------------|
| 1 | Reasonably exhaustive research | Standards Critic |
| 2 | Complete and accurate citations | Standards Critic |
| 3 | Thorough analysis and correlation | Reasoning Critic |
| 4 | Resolution of conflicting evidence | Reasoning Critic |
| 5 | Soundly written conclusions | Standards Critic |

### Confidence Thresholds

| Threshold | Action |
|-----------|--------|
| ≥ 0.85 | Auto-accept (with user notification) |
| 0.70 - 0.84 | Accept with notes |
| 0.50 - 0.69 | Search Revision Request |
| < 0.50 | Reject (insufficient evidence) |

### Search Revision Request

When confidence falls below 0.70:

```json
{
  "type": "SEARCH_REVISION_REQUEST",
  "fact_id": "uuid",
  "current_confidence": 0.62,
  "required_confidence": 0.70,
  "deficiencies": [
    {
      "pillar": 1,
      "issue": "Only one repository searched",
      "suggestion": "Search Belgian church records pre-1796"
    },
    {
      "pillar": 4,
      "issue": "Conflicting death dates",
      "suggestion": "Obtain death certificate to resolve"
    }
  ],
  "assigned_to": "research_agent"
}
```

---

## 10. Implementation Decisions

### Open Questions

1. **Message Bus Technology**
   - Options: Redis Streams, RabbitMQ, In-process queues
   - Consideration: Single-user vs multi-user deployment

2. **Search Index Technology**
   - Options: Tantivy (Rust, embedded), Meilisearch (server), SQLite FTS5
   - Consideration: Fuzzy name matching requirements

3. **Gramps Sync Mechanism**
   - Options: Direct DB access, Gramps Web API, File export/import
   - Consideration: Real-time vs batch sync

4. **API Rate Limiting**
   - FamilySearch: 1000 requests/day (free tier)
   - Ancestry: Requires subscription
   - Strategy: Prioritize, cache aggressively

5. **Cost Management**
   - Opus calls are expensive
   - Strategy: Haiku for pre-filtering, Sonnet for coordination, Opus only for judgment

### Recommended Implementation Order

1. **Phase 1: Core Infrastructure**
   - Fact Ledger (RocksDB)
   - Basic Workflow Agent
   - Single GPS Critic (combined)
   - CLI interface

2. **Phase 2: Research Pipeline**
   - Research Agent
   - FamilySearch integration
   - Data Quality Agent
   - Split GPS Critics

3. **Phase 3: User Interfaces**
   - Approval Queue (web)
   - Dashboard
   - Chat interface

4. **Phase 4: Advanced Features**
   - Translation Agent
   - Ethnicity/DNA Agent
   - Gramps sync
   - Additional source integrations

5. **Phase 5: Polish**
   - Synthesis Agent
   - Full GPS reporting
   - Performance optimization

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **GPS** | Genealogical Proof Standard - BCG's standard for acceptable conclusions |
| **BCG** | Board for Certification of Genealogists |
| **CQRS** | Command Query Responsibility Segregation - separate read/write models |
| **Fact** | A single piece of genealogical information with provenance |
| **Ledger** | Immutable append-only storage for facts |
| **Projection** | Read-optimized view built from the ledger |
| **Critique** | GPS Critic's assessment of a proposed fact |
| **Confidence Delta** | Adjustment to fact confidence based on critique |

---

## Appendix B: Example Fact Record

```json
{
  "fact_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": 1,
  "record_id": "660e8400-e29b-41d4-a716-446655440001",
  "supersedes": null,

  "fact_type": "birth",
  "subject_person_id": "770e8400-e29b-41d4-a716-446655440002",
  "content": {
    "date": "1850-03-15",
    "place": "Tervuren, Brabant, Belgium",
    "father_name": "Pierre Herinckx",
    "mother_name": "Marie Janssens"
  },

  "source_citations": [
    {
      "formatted_full": "Belgium, Brabant, Tervuren, Civil Registration, Births, 1850, entry 45, Jean Joseph Herinckx; Belgian State Archives, Brussels.",
      "source_level": "primary",
      "repository": "Belgian State Archives"
    }
  ],
  "proposed_by": "research_agent",
  "extraction_method": "api:belgian_archives",

  "initial_confidence": 0.85,
  "confidence_deltas": [
    {
      "applied_by": "gps_standards_critic",
      "delta": -0.05,
      "reason": "Missing repository call number",
      "timestamp": "2026-01-17T10:30:00Z"
    }
  ],
  "final_confidence": 0.80,
  "status": "accepted",

  "created_at": "2026-01-17T10:00:00Z",
  "status_changed_at": "2026-01-17T10:35:00Z",
  "status_change_reason": "Confidence 0.80 meets threshold. Primary source, direct evidence.",

  "corroborates": [],
  "conflicts_with": [],
  "conflict_resolution": null
}
```

---

**Document Status:** Ready for architectural review

**Next Steps:**
1. Review and approve architecture
2. Finalize open implementation decisions
3. Create detailed implementation plan
4. Begin Phase 1 development
