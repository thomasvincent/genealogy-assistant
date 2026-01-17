# Genealogy Research Assistant

AI-powered genealogy research assistant following BCG certification standards and the Genealogical Proof Standard (GPS).

## Features

- **GPS-Compliant AI Research** - Claude-powered assistant enforcing source hierarchy
- **Multi-Provider Search** - FamilySearch, Geneanet, Belgian Archives, FindAGrave
- **GEDCOM Management** - Load, validate, search, and export GEDCOM files
- **Gramps Integration** - Local database and Gramps Web API support
- **Report Generation** - Proof summaries, research logs, family sheets, pedigree charts

## Quick Start

```bash
# Install dependencies
uv sync

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run CLI
uv run python -m genealogy_assistant.cli --help

# Run web server
uv run uvicorn genealogy_assistant.web:app --reload
```

## Docker

```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
docker compose up -d
```

## License

MIT
