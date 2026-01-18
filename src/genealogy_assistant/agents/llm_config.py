"""LLM configuration for AutoGen agents."""

from __future__ import annotations

import os
from typing import Any

from autogen_core.models import ChatCompletionClient


def get_llm_config(
    provider: str = "anthropic",
    model: str | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """
    Get LLM configuration for AutoGen agents.

    Args:
        provider: LLM provider ("anthropic", "openai", "azure", "ollama")
        model: Specific model to use (defaults based on provider)
        temperature: Sampling temperature (0.0-1.0)

    Returns:
        Configuration dict containing model_client
    """
    model_client = create_model_client(provider, model, temperature)

    return {
        "model_client": model_client,
        "provider": provider,
        "model": model or _get_default_model(provider),
        "temperature": temperature,
    }


def create_model_client(
    provider: str = "anthropic",
    model: str | None = None,
    temperature: float = 0.3,
) -> ChatCompletionClient:
    """
    Create a model client for the specified provider.

    Args:
        provider: LLM provider ("anthropic", "openai", "azure", "ollama")
        model: Specific model to use (defaults based on provider)
        temperature: Sampling temperature (0.0-1.0)

    Returns:
        ChatCompletionClient instance
    """
    provider = provider.lower()

    if provider == "anthropic":
        from autogen_ext.models.anthropic import AnthropicChatCompletionClient

        return AnthropicChatCompletionClient(
            model=model or "claude-sonnet-4-20250514",
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            temperature=temperature,
        )

    elif provider == "openai":
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=model or "gpt-4-turbo",
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=temperature,
        )

    elif provider == "azure":
        from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

        return AzureOpenAIChatCompletionClient(
            model=model or "gpt-4",
            azure_deployment=model or "gpt-4",
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview",
            temperature=temperature,
        )

    elif provider == "ollama":
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        # Ollama uses OpenAI-compatible API
        return OpenAIChatCompletionClient(
            model=model or "llama3:70b",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",  # Ollama doesn't require real key
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Choose from: anthropic, openai, azure, ollama"
        )


def _get_default_model(provider: str) -> str:
    """Get the default model for a provider."""
    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4-turbo",
        "azure": "gpt-4",
        "ollama": "llama3:70b",
    }
    return defaults.get(provider, "gpt-4-turbo")


def validate_api_key(provider: str) -> bool:
    """Check if required API key is set for provider."""
    key_mapping = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "ollama": None,  # No key required
    }

    env_var = key_mapping.get(provider)
    if env_var is None:
        return True  # No key required

    return bool(os.environ.get(env_var))


def get_available_providers() -> list[str]:
    """Get list of providers with valid API keys configured."""
    providers = ["anthropic", "openai", "azure", "ollama"]
    return [p for p in providers if validate_api_key(p)]
