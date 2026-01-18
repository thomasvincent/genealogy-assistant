"""AutoGen multi-agent system for genealogy research."""

from genealogy_assistant.agents.config import (
    create_genealogy_agents,
    create_research_group_chat,
    create_simple_research_chain,
)
from genealogy_assistant.agents.llm_config import (
    create_model_client,
    get_llm_config,
    validate_api_key,
    get_available_providers,
)
from genealogy_assistant.agents.prompts import AgentPrompts, PROMPTS

__all__ = [
    "AgentPrompts",
    "PROMPTS",
    "create_genealogy_agents",
    "create_model_client",
    "create_research_group_chat",
    "create_simple_research_chain",
    "get_available_providers",
    "get_llm_config",
    "validate_api_key",
]
