"""Tests for AI research assistant."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from genealogy_assistant.api.assistant import (
    GenealogyAssistant,
    AssistantConfig,
    AssistantResponse,
    ResearchTask,
    ResearchMode,
)
from genealogy_assistant.core.models import ConfidenceLevel, Name, Person


class TestAssistantConfig:
    """Tests for AssistantConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AssistantConfig()

        # model is None by default (uses provider default)
        assert config.model is None
        assert config.llm_provider == "anthropic"
        assert config.temperature == 0.3

    def test_custom_config(self):
        """Test custom configuration."""
        config = AssistantConfig(
            llm_provider="openai",
            model="gpt-4-turbo",
            temperature=0.5,
        )

        assert config.llm_provider == "openai"
        assert config.model == "gpt-4-turbo"
        assert config.temperature == 0.5

    def test_legacy_config(self):
        """Test legacy configuration conversion."""
        config = AssistantConfig.from_legacy(
            model="claude-opus-4-20250514",
            temperature=0.5,
        )

        assert config.llm_provider == "anthropic"
        assert config.model == "claude-opus-4-20250514"
        assert config.temperature == 0.5

    def test_research_mode_config(self):
        """Test research mode configuration."""
        simple_config = AssistantConfig(mode=ResearchMode.SIMPLE)
        assert simple_config.mode == ResearchMode.SIMPLE

        collab_config = AssistantConfig(mode=ResearchMode.COLLABORATIVE)
        assert collab_config.mode == ResearchMode.COLLABORATIVE


class TestAssistantResponse:
    """Tests for AssistantResponse parsing."""

    def test_response_creation(self):
        """Test creating assistant response."""
        response = AssistantResponse(
            message="Test response",
            confidence=ConfidenceLevel.STRONG,
            next_actions=["Search census records", "Check vital records"],
            ai_assisted=True,
        )

        assert response.message == "Test response"
        assert response.confidence == ConfidenceLevel.STRONG
        assert len(response.next_actions) == 2

    def test_default_confidence(self):
        """Test default confidence level."""
        response = AssistantResponse(message="Test")
        assert response.confidence == ConfidenceLevel.REASONABLE

    def test_response_with_agent_contributions(self):
        """Test response with multi-agent contributions."""
        response = AssistantResponse(
            message="Collaborative result",
            agent_contributions={
                "ResearchCoordinator": "Analysis complete",
                "SourceEvaluator": "Sources verified",
            },
        )

        assert len(response.agent_contributions) == 2
        assert "ResearchCoordinator" in response.agent_contributions

    def test_response_with_tools_used(self):
        """Test response with tools used tracking."""
        response = AssistantResponse(
            message="Search complete",
            tools_used=["search.search_person", "gps.validate_proof"],
        )

        assert len(response.tools_used) == 2
        assert "search.search_person" in response.tools_used


class TestResearchTask:
    """Tests for ResearchTask."""

    def test_task_creation(self):
        """Test creating research task."""
        task = ResearchTask(
            task_type="identify",
            description="Identify parents of Jean Joseph Herinckx",
        )

        assert task.task_type == "identify"
        assert task.description == "Identify parents of Jean Joseph Herinckx"
        assert task.status == "pending"

    def test_task_with_person(self):
        """Test task with target person."""
        person = Person()
        person.id = "I001"
        person.names.append(Name(surname="HERINCKX", given="Jean"))

        task = ResearchTask(
            task_type="verify",
            description="Verify birth date",
            target_person=person,
        )

        assert task.target_person is not None
        assert task.target_person.id == "I001"


class TestGenealogyAssistant:
    """Tests for GenealogyAssistant class."""

    @pytest.fixture
    def mock_kernel(self):
        """Create mock Semantic Kernel."""
        kernel = MagicMock()
        kernel.get_service.return_value = MagicMock()
        kernel.get_prompt_execution_settings_class.return_value = MagicMock
        kernel.invoke = AsyncMock(return_value="Mock result")
        return kernel

    @pytest.fixture
    def mock_chat_service(self):
        """Create mock chat completion service."""
        service = MagicMock()
        service.get_chat_message_content = AsyncMock(
            return_value="Based on the evidence, this is a test response."
        )
        return service

    @pytest.mark.asyncio
    async def test_research_basic(self, mock_kernel, mock_chat_service):
        """Test basic research query."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            config = AssistantConfig()
            assistant = GenealogyAssistant(config)
            await assistant.connect()

            response = await assistant.research("When was Jean Joseph Herinckx born?")

            assert response.message is not None
            assert response.ai_assisted is True
            mock_chat_service.get_chat_message_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_with_context(self, mock_kernel, mock_chat_service):
        """Test research with context."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            config = AssistantConfig()
            assistant = GenealogyAssistant(config)
            await assistant.connect()

            context = {"known_facts": ["Born in Belgium", "Emigrated to USA"]}
            response = await assistant.research(
                "What records should I search?",
                context=context,
            )

            assert response.message is not None

    @pytest.mark.asyncio
    async def test_parse_confidence_from_response(self, mock_kernel):
        """Test parsing confidence level from response."""
        # Create mock chat service with confidence indicator
        mock_chat_service = MagicMock()
        mock_chat_service.get_chat_message_content = AsyncMock(
            return_value="Based on the evidence, this conclusion is PROVEN with Confidence: 5"
        )
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            response = await assistant.research("Test question")

            assert response.confidence == ConfidenceLevel.GPS_COMPLETE

    @pytest.mark.asyncio
    async def test_parse_next_actions(self, mock_kernel):
        """Test parsing next actions from response."""
        response_text = """Analysis complete.

## Next Research Actions
- Search Tervuren birth records
- Check FamilySearch Belgium collection
- Contact Rijksarchief Leuven
"""
        mock_chat_service = MagicMock()
        mock_chat_service.get_chat_message_content = AsyncMock(return_value=response_text)
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            response = await assistant.research("Test question")

            assert len(response.next_actions) >= 1
            assert any("Tervuren" in a for a in response.next_actions)

    @pytest.mark.asyncio
    async def test_reset_conversation(self, mock_kernel, mock_chat_service):
        """Test conversation reset."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            # Add some messages
            await assistant.research("Question 1")
            await assistant.research("Question 2")

            initial_len = len(assistant._chat_history.messages)
            assert initial_len >= 2

            # Reset
            assistant.reset_conversation()

            # Should only have system message
            assert len(assistant._chat_history.messages) == 1

    @pytest.mark.asyncio
    async def test_create_research_plan(self, mock_kernel, mock_chat_service):
        """Test research plan generation."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            target = Person()
            target.names.append(Name(surname="HERINCKX", given="Jean"))

            response = await assistant.create_research_plan(target, "Find parents")

            assert response.message is not None

    @pytest.mark.asyncio
    async def test_verify_conclusion(self, mock_kernel, mock_chat_service):
        """Test conclusion verification."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            response = await assistant.verify_conclusion(
                "Jean Joseph Herinckx was born 15 March 1895",
                ["Birth certificate from Tervuren", "Census 1900 showing age 5"],
            )

            assert response.message is not None

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_kernel, mock_chat_service):
        """Test async context manager protocol."""
        mock_kernel.get_service.return_value = mock_chat_service

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            async with GenealogyAssistant(AssistantConfig()) as assistant:
                assert assistant._kernel is not None

            assert assistant._kernel is None

    @pytest.mark.asyncio
    async def test_get_kernel_info(self, mock_kernel, mock_chat_service):
        """Test kernel info retrieval."""
        mock_kernel.get_service.return_value = mock_chat_service
        mock_kernel.services = {"chat": mock_chat_service}
        mock_kernel.plugins = {}

        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel

            assistant = GenealogyAssistant(AssistantConfig())

            # Before connect
            info = assistant.get_kernel_info()
            assert info["status"] == "not_connected"

            # After connect
            with patch("genealogy_assistant.api.assistant.get_kernel_info") as mock_info:
                mock_info.return_value = {"services": ["chat"], "plugins": []}
                await assistant.connect()
                info = assistant.get_kernel_info()
                assert "services" in info


class TestAssistantPlugins:
    """Tests for assistant plugin methods."""

    @pytest.fixture
    def mock_kernel_with_plugins(self):
        """Create mock Semantic Kernel with plugins."""
        kernel = MagicMock()
        kernel.get_service.return_value = MagicMock()
        kernel.get_prompt_execution_settings_class.return_value = MagicMock
        kernel.invoke = AsyncMock(return_value="Plugin result")
        return kernel

    @pytest.mark.asyncio
    async def test_generate_proof_summary(self, mock_kernel_with_plugins):
        """Test proof summary generation via plugin."""
        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel_with_plugins

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            result = await assistant.generate_proof_summary(
                research_question="Who were the parents?",
                conclusion="Parents were identified",
                evidence=["Birth cert", "Census"],
                confidence=4,
            )

            assert result is not None
            mock_kernel_with_plugins.invoke.assert_called()

    @pytest.mark.asyncio
    async def test_format_citation(self, mock_kernel_with_plugins):
        """Test citation formatting via plugin."""
        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel_with_plugins

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            result = await assistant.format_citation(
                record_type="vital",
                jurisdiction="Tervuren, Brabant, Belgium",
                date="1895-03-15",
                person_name="Jean Joseph HERINCKX",
                repository="Rijksarchief Leuven",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_remember_person(self, mock_kernel_with_plugins):
        """Test remembering a person via memory plugin."""
        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel_with_plugins

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            result = await assistant.remember_person(
                person_name="Jean Joseph HERINCKX",
                birth_info="15 Mar 1895, Tervuren",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_recall_person(self, mock_kernel_with_plugins):
        """Test recalling a person via memory plugin."""
        with patch("genealogy_assistant.api.assistant.create_kernel") as mock_create_kernel:
            mock_create_kernel.return_value = mock_kernel_with_plugins

            assistant = GenealogyAssistant(AssistantConfig())
            await assistant.connect()

            result = await assistant.recall_person(query="Herinckx Tervuren")

            assert result is not None
