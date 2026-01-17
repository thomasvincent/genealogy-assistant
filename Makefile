.PHONY: help install dev test lint format type-check check clean docker-up docker-down docker-logs docker-build

PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff
MYPY := uv run mypy

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Install with dev dependencies
	uv sync --dev

test: ## Run tests
	$(PYTEST) tests/ -v

test-cov: ## Run tests with coverage
	$(PYTEST) tests/ -v --cov=src/genealogy_assistant --cov-report=html --cov-report=term

lint: ## Run linter
	$(RUFF) check src/ tests/

format: ## Format code
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

type-check: ## Run type checker
	$(MYPY) src/

check: lint type-check test ## Run all checks (lint, type-check, test)

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Docker commands
docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start all services
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## View logs
	docker compose logs -f

docker-restart: ## Restart all services
	docker compose restart

docker-clean: ## Remove all containers and volumes
	docker compose down -v --remove-orphans

# Development shortcuts
run-api: ## Run FastAPI server locally
	$(PYTHON) -m uvicorn genealogy_assistant.web:app --reload --host 0.0.0.0 --port 8000

run-cli: ## Run CLI
	$(PYTHON) -m genealogy_assistant.cli

# Pre-commit
pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run: ## Run pre-commit on all files
	uv run pre-commit run --all-files
