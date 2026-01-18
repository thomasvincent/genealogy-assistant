"""Semantic Kernel initialization and configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import semantic_kernel as sk
from semantic_kernel.connectors.ai.anthropic import AnthropicChatCompletion
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatCompletion

if TYPE_CHECKING:
    from semantic_kernel.memory import SemanticTextMemory


@dataclass
class KernelConfig:
    """Configuration for Semantic Kernel."""

    # LLM provider configuration
    llm_provider: str = "anthropic"  # anthropic, openai, azure, ollama
    model: str | None = None  # Uses provider default if None
    temperature: float = 0.3

    # Memory configuration
    enable_memory: bool = True
    memory_persist_directory: str = "./genealogy_memory"

    # Plugin configuration
    enable_search_plugins: bool = True
    enable_gedcom_plugin: bool = True
    enable_report_plugins: bool = True
    enable_gps_plugin: bool = True

    # Search provider configuration
    search_providers: list[str] = field(
        default_factory=lambda: ["familysearch", "geneanet", "findagrave"]
    )


async def create_kernel(config: KernelConfig | None = None) -> sk.Kernel:
    """
    Create and configure a Semantic Kernel instance.

    Args:
        config: Kernel configuration (uses defaults if None)

    Returns:
        Configured Semantic Kernel instance
    """
    config = config or KernelConfig()
    kernel = sk.Kernel()

    # Add LLM service based on provider
    _add_llm_service(kernel, config)

    # Add plugins
    if config.enable_search_plugins:
        _add_search_plugins(kernel, config)

    if config.enable_gedcom_plugin:
        _add_gedcom_plugin(kernel)

    if config.enable_gps_plugin:
        _add_gps_plugin(kernel)

    if config.enable_report_plugins:
        _add_report_plugins(kernel)

    # Add memory if enabled
    if config.enable_memory:
        await _add_memory(kernel, config)

    return kernel


def _add_llm_service(kernel: sk.Kernel, config: KernelConfig) -> None:
    """Add LLM service to kernel based on provider."""
    provider = config.llm_provider.lower()

    if provider == "anthropic":
        model = config.model or "claude-sonnet-4-20250514"
        kernel.add_service(
            AnthropicChatCompletion(
                service_id="chat",
                ai_model_id=model,
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
            )
        )

    elif provider == "openai":
        model = config.model or "gpt-4-turbo"
        kernel.add_service(
            OpenAIChatCompletion(
                service_id="chat",
                ai_model_id=model,
                api_key=os.environ.get("OPENAI_API_KEY"),
            )
        )

    elif provider == "azure":
        model = config.model or "gpt-4"
        kernel.add_service(
            AzureChatCompletion(
                service_id="chat",
                deployment_name=model,
                endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            )
        )

    elif provider == "ollama":
        # Ollama uses OpenAI-compatible API
        model = config.model or "llama3:70b"
        kernel.add_service(
            OpenAIChatCompletion(
                service_id="chat",
                ai_model_id=model,
                api_key="ollama",  # Dummy key
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            )
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _add_search_plugins(kernel: sk.Kernel, config: KernelConfig) -> None:
    """Add search plugins to kernel."""
    from genealogy_assistant.plugins.search import UnifiedSearchPlugin

    kernel.add_plugin(
        UnifiedSearchPlugin(providers=config.search_providers),
        plugin_name="search",
    )


def _add_gedcom_plugin(kernel: sk.Kernel) -> None:
    """Add GEDCOM plugin to kernel."""
    from genealogy_assistant.plugins.gedcom import GedcomPlugin

    kernel.add_plugin(GedcomPlugin(), plugin_name="gedcom")


def _add_gps_plugin(kernel: sk.Kernel) -> None:
    """Add GPS validation plugin to kernel."""
    from genealogy_assistant.plugins.gps import GPSValidationPlugin

    kernel.add_plugin(GPSValidationPlugin(), plugin_name="gps")


def _add_report_plugins(kernel: sk.Kernel) -> None:
    """Add report generation plugins to kernel."""
    from genealogy_assistant.plugins.reports import (
        CitationsPlugin,
        ProofSummaryPlugin,
    )

    kernel.add_plugin(ProofSummaryPlugin(), plugin_name="reports")
    kernel.add_plugin(CitationsPlugin(), plugin_name="citations")


async def _add_memory(kernel: sk.Kernel, config: KernelConfig) -> None:
    """Add memory/RAG capabilities to kernel."""
    try:
        from chromadb import PersistentClient
        from semantic_kernel.connectors.memory.chroma import ChromaMemoryStore
        from semantic_kernel.memory import SemanticTextMemory

        from genealogy_assistant.plugins.memory import ResearchMemoryPlugin

        # Create ChromaDB client
        chroma_client = PersistentClient(path=config.memory_persist_directory)

        # Create memory store
        memory_store = ChromaMemoryStore(chroma_client=chroma_client)

        # Create semantic memory
        # Note: This requires an embedding service - we'll use the chat service
        memory = SemanticTextMemory(
            storage=memory_store,
            embeddings_generator=kernel.get_service("chat"),
        )

        # Add memory plugin
        kernel.add_plugin(
            ResearchMemoryPlugin(memory=memory),
            plugin_name="memory",
        )

    except ImportError:
        # ChromaDB not installed, skip memory
        pass
    except Exception:
        # Memory initialization failed, continue without it
        pass


def get_kernel_info(kernel: sk.Kernel) -> dict:
    """Get information about kernel configuration."""
    return {
        "services": list(kernel.services.keys()),
        "plugins": list(kernel.plugins.keys()),
        "functions": {
            plugin_name: list(plugin.functions.keys())
            for plugin_name, plugin in kernel.plugins.items()
        },
    }
