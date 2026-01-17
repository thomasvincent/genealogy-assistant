# Contributing to Genealogy Assistant

Thank you for your interest in contributing! This project aims to provide GPS/BCG-compliant genealogy research tools.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (optional, for running Gramps Web)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/thomasvincent/genealogy-assistant.git
cd genealogy-assistant

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linter
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Using Docker

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

## Code Style

- **Formatter**: ruff (run `uv run ruff format`)
- **Linter**: ruff (run `uv run ruff check`)
- **Type hints**: Required for all public functions
- **Docstrings**: Google style

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new search provider
fix: resolve date parsing issue
docs: update API documentation
test: add tests for GPS validation
refactor: simplify router logic
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Make your changes
4. Run tests and linting (`make check`)
5. Commit with conventional commit message
6. Push to your fork
7. Open a Pull Request

## Areas for Contribution

### Source Registry
Add new genealogical databases to `src/genealogy_assistant/data/sources.yaml`:
- Regional archives (state, county, parish)
- Ethnic-specific sources (Cherokee rolls, Jewish records, etc.)
- Immigration/emigration records

### Search Providers
Implement new search provider integrations in `src/genealogy_assistant/search/providers/`.

### Gramps Plugin
Improve the Gramps desktop plugin in `src/genealogy_assistant/adapters/gramps_plugin/`.

### Documentation
- Usage examples
- API documentation
- Genealogy methodology guides

## Genealogical Standards

All contributions must maintain GPS (Genealogical Proof Standard) compliance:

1. **Source hierarchy**: Primary > Secondary > Tertiary
2. **Evidence classification**: Direct, Indirect, Negative
3. **Confidence scoring**: 1-5 scale per BCG standards
4. **Citation format**: Evidence Explained style

## Questions?

Open an issue or start a discussion. We're happy to help!
