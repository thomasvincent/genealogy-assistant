"""AutoGen agent configuration and creation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination

from genealogy_assistant.agents.prompts import PROMPTS

if TYPE_CHECKING:
    from semantic_kernel import Kernel


def create_genealogy_agents(
    llm_config: dict[str, Any],
    kernel: "Kernel | None" = None,
) -> dict[str, AssistantAgent | UserProxyAgent]:
    """
    Create the genealogy research agent team.

    Args:
        llm_config: LLM configuration from get_llm_config()
        kernel: Optional Semantic Kernel instance for plugin access

    Returns:
        Dictionary of agent name -> agent instance
    """
    # Extract model client from config
    model_client = llm_config.get("model_client")

    # Research Coordinator - primary orchestrating agent
    coordinator = AssistantAgent(
        name="ResearchCoordinator",
        system_message=PROMPTS.RESEARCH_COORDINATOR,
        model_client=model_client,
    )

    # Source Evaluator - classifies sources by GPS hierarchy
    source_evaluator = AssistantAgent(
        name="SourceEvaluator",
        system_message=PROMPTS.SOURCE_EVALUATOR,
        model_client=model_client,
    )

    # Conflict Resolver - handles evidence conflicts
    conflict_resolver = AssistantAgent(
        name="ConflictResolver",
        system_message=PROMPTS.CONFLICT_RESOLVER,
        model_client=model_client,
    )

    # Report Writer - generates GPS-compliant reports
    report_writer = AssistantAgent(
        name="ReportWriter",
        system_message=PROMPTS.REPORT_WRITER,
        model_client=model_client,
    )

    # DNA Analyst - interprets genetic genealogy
    dna_analyst = AssistantAgent(
        name="DNAAnalyst",
        system_message=PROMPTS.DNA_ANALYST,
        model_client=model_client,
    )

    # Paleographer - transcribes historical handwriting
    paleographer = AssistantAgent(
        name="Paleographer",
        system_message=PROMPTS.PALEOGRAPHER,
        model_client=model_client,
    )

    # Record Locator - finds archive holdings
    record_locator = AssistantAgent(
        name="RecordLocator",
        system_message=PROMPTS.RECORD_LOCATOR,
        model_client=model_client,
    )

    # Archive Specialist - regional expertise
    archive_specialist = AssistantAgent(
        name="ArchiveSpecialist",
        system_message=PROMPTS.ARCHIVE_SPECIALIST,
        model_client=model_client,
    )

    # User Proxy - represents the human user
    user_proxy = UserProxyAgent(
        name="User",
    )

    agents = {
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

    # Register Semantic Kernel tools if kernel provided
    if kernel is not None:
        _register_sk_tools(agents, kernel)

    return agents


def _register_sk_tools(
    agents: dict[str, AssistantAgent | UserProxyAgent],
    kernel: "Kernel",
) -> None:
    """Register Semantic Kernel plugins as AutoGen tools."""
    # Get all registered plugins from kernel
    plugins = kernel.plugins

    for plugin_name, plugin in plugins.items():
        # Convert SK functions to AutoGen tool format
        for func_name, func in plugin.functions.items():
            tool_wrapper = _create_tool_wrapper(kernel, plugin_name, func_name)

            # Register with agents that need tools
            # Coordinator and RecordLocator get search tools
            if plugin_name == "search":
                agents["coordinator"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)
                agents["record_locator"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)

            # GPS validation goes to coordinator and source_evaluator
            elif plugin_name == "gps":
                agents["coordinator"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)
                agents["source_evaluator"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)

            # GEDCOM tools for coordinator
            elif plugin_name == "gedcom":
                agents["coordinator"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)

            # Report tools for report_writer
            elif plugin_name in ("reports", "citations"):
                agents["report_writer"].register_for_llm(
                    name=f"{plugin_name}_{func_name}",
                    description=func.description or f"{plugin_name}.{func_name}",
                )(tool_wrapper)


def _create_tool_wrapper(kernel: "Kernel", plugin_name: str, func_name: str):
    """Create a wrapper function that calls the SK plugin."""

    async def wrapper(**kwargs):
        result = await kernel.invoke(
            plugin_name=plugin_name,
            function_name=func_name,
            **kwargs,
        )
        return str(result)

    return wrapper


def create_research_group_chat(
    agents: dict[str, AssistantAgent | UserProxyAgent],
    model_client,
    max_rounds: int = 20,
) -> SelectorGroupChat:
    """
    Create a multi-agent group chat for genealogy research.

    Args:
        agents: Dictionary of agents from create_genealogy_agents()
        model_client: Model client for selector decisions
        max_rounds: Maximum conversation rounds

    Returns:
        SelectorGroupChat instance
    """
    # Order matters - coordinator first to orchestrate
    agent_list = [
        agents["coordinator"],
        agents["source_evaluator"],
        agents["conflict_resolver"],
        agents["report_writer"],
        agents["dna_analyst"],
        agents["paleographer"],
        agents["record_locator"],
        agents["archive_specialist"],
    ]

    # Selector prompt to guide agent selection
    selector_prompt = """You are orchestrating a genealogy research team. Based on the current conversation,
select the most appropriate agent to respond next.

- ResearchCoordinator: Orchestrates research, creates plans, synthesizes findings
- SourceEvaluator: Classifies sources as primary/secondary/tertiary, evaluates evidence quality
- ConflictResolver: Resolves conflicting evidence between sources
- ReportWriter: Generates GPS-compliant proof summaries and citations
- DNAAnalyst: Interprets DNA matches and genetic evidence
- Paleographer: Transcribes handwritten historical documents
- RecordLocator: Finds relevant archives and repositories
- ArchiveSpecialist: Has regional expertise in European and US archives

Select the agent whose expertise best matches what's needed next."""

    termination = MaxMessageTermination(max_messages=max_rounds)

    group_chat = SelectorGroupChat(
        participants=agent_list,
        model_client=model_client,
        termination_condition=termination,
        selector_prompt=selector_prompt,
    )

    return group_chat


def create_simple_research_chain(
    model_client,
) -> AssistantAgent:
    """
    Create a simple single-agent researcher (for simpler queries).

    Returns:
        Combined researcher agent
    """
    # Combined researcher with full GPS knowledge
    researcher = AssistantAgent(
        name="GenealogyResearcher",
        system_message=f"""{PROMPTS.RESEARCH_COORDINATOR}

Additionally, you have the following specialist knowledge integrated:

SOURCE EVALUATION:
{PROMPTS.SOURCE_EVALUATOR}

CONFLICT RESOLUTION:
{PROMPTS.CONFLICT_RESOLVER}

You can handle straightforward research questions directly without delegation.""",
        model_client=model_client,
    )

    return researcher
