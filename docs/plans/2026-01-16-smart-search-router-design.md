# Smart Search Router Design

**Date:** 2026-01-16
**Status:** Approved

## Overview

Build a Smart Search Router that automatically searches the right genealogical databases based on person context (location, time period, ethnicity). Uses a hybrid approach: rule-based routing for common patterns, AI fallback for complex cases.

## Problem Statement

Finding records across multiple databases is the biggest pain point. Users don't know which databases to search for a given time period/location. This is especially complex with:
- Cherokee records (Dawes Rolls, Baker Roll, etc. - specific date ranges)
- Belgian records (civil registration started 1796, church records before)
- US records varying by state and era

## Architecture: Library + Adapters

Core logic as a reusable library with platform-specific adapters:

```
genealogy-assistant/
│
├── genealogy_core/              # CORE LIBRARY (no UI dependencies)
│   ├── models.py                # Data models
│   ├── router/
│   │   ├── registry.py          # Source registry
│   │   └── smart_router.py      # Routing logic
│   ├── ai/
│   │   └── claude_client.py     # Claude integration
│   └── search/
│       └── providers/           # Search providers
│
├── adapters/
│   ├── gramps_plugin/           # GRAMPS DESKTOP PLUGIN
│   │   ├── __init__.py
│   │   ├── smart_search.gpr.py  # Plugin registration
│   │   └── smart_search.py      # GTK UI wrapper
│   │
│   └── gramps_web/              # GRAMPS WEB INTEGRATION
│       ├── api.py               # FastAPI endpoints
│       └── client.py            # Gramps Web API client
│
└── cli.py                       # Command-line interface
```

**Key principle:** Core library has zero UI dependencies - pure Python logic. Adapters wrap it for specific platforms.

## Component 1: Source Registry

Structured knowledge base of genealogical sources stored as YAML:

```yaml
sources:
  belgian_state_archives:
    name: Belgian State Archives
    url: https://search.arch.be
    coverage:
      geographic: [Belgium]
      temporal: {start: 1796, end: 1912}
    record_types: [civil_registration, census]
    source_level: primary

  dawes_rolls:
    name: Dawes Rolls
    url: https://www.archives.gov/research/native-americans/dawes
    coverage:
      geographic: [Cherokee Nation, Indian Territory]
      temporal: {start: 1898, end: 1914}
    record_types: [enrollment]
    source_level: primary
    ethnic_markers: [Cherokee, Creek, Choctaw, Chickasaw, Seminole]
```

## Component 2: Smart Router Logic

```
Input: Person (name, birth date/place, death date/place, ethnicity hints)
           ↓
┌─────────────────────────────────────────┐
│         Context Extractor               │
│  • Extract locations (Belgium, Cherokee)│
│  • Extract time ranges (1850-1920)      │
│  • Detect ethnic/cultural markers       │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│         Rule-Based Matcher              │
│  • Match location → relevant archives   │
│  • Match time → available record types  │
│  • Filter by source level (primary first)│
└─────────────────────────────────────────┘
           ↓
   Rules found?  ──No──→  AI Fallback
        │                 (Claude analyzes
       Yes                 complex cases)
        ↓
┌─────────────────────────────────────────┐
│         Priority Scorer                 │
│  • Primary sources first                │
│  • Original images > transcripts        │
│  • Specific > general databases         │
└─────────────────────────────────────────┘
           ↓
Output: Prioritized list of (Database, SearchParams, Priority)
```

### Key Routing Rules

| Context | Source |
|---------|--------|
| Belgian birth before 1796 | Church records (Catholic parish registers) |
| Belgian birth 1796+ | State Archives civil registration |
| Cherokee ancestry | Dawes Rolls, Baker Roll, Chapman Roll (by date) |
| US Census 1790-1950 | FamilySearch |
| Belgian emigration 1850-1920 | Antwerp Red Star Line, Castle Garden |

## Component 3: AI Fallback

Triggers when:
- No rules match the location/time combination
- Person has multiple countries in history (migration)
- Ethnic markers suggest specialized sources

```python
SourceRecommendation(
    database="Castle Garden / Ellis Island",
    reason="Belgian emigration to US in 1880s",
    priority=1,
    record_types=["passenger manifest"],
    search_params={"surname": "Herinckx", "year_range": "1875-1890"}
)
```

## Implementation Phases

### Phase 1: Foundation
1. Create `sources.yaml` with initial sources
2. Build `registry.py` to load and query sources
3. Add `SourceRecommendation` model

### Phase 2: Router
4. Build `smart_router.py` with rule-based matching
5. Integrate AI fallback via Claude
6. Add caching for AI recommendations

### Phase 3: Integration
7. Update unified search to use router
8. Add CLI command: `genealogy search --smart <person>`
9. Add API endpoint: `POST /search/smart`

### Phase 4: Gramps Plugin
10. Create Gramps desktop plugin adapter
11. GTK UI for smart search
12. Register as Gramps tool

### Phase 5: Cleanup
13. Refactor providers into `providers/` directory
14. Standardize interfaces and type hints
15. Add comprehensive tests

## Success Criteria

- Given a person, router returns relevant sources in <100ms (rule-based)
- AI fallback responds in <3s for complex cases
- Primary sources always ranked before tertiary
- Works with both Gramps Desktop and Gramps Web
