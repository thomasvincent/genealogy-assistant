"""Tests for AI research assistant."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from genealogy_assistant.api.assistant import (
    GenealogyAssistant,
    AssistantConfig,
    AssistantResponse,
    ResearchTask,
)
from genealogy_assistant.core.models import ConfidenceLevel, Name, Person


class TestAssistantConfig:
    """Tests for AssistantConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AssistantConfig()

        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.temperature == 0.3

    def test_custom_config(self):
        """Test custom configuration."""
        config = AssistantConfig(
            api_key="test-key",
            model="claude-opus-4-20250514",
            max_tokens=8192,
            temperature=0.5,
        )

        assert config.api_key == "test-key"
        assert config.model == "claude-opus-4-20250514"
        assert config.max_tokens == 8192


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


class TestResearchTask:
    """Tests for ResearchTask."""

    def test_task_creation(self):
        """Test creating research task."""
        task = ResearchTask(
            task_type="identify",
            description="Identify parents of Jean Joseph Herinckx",
            known_facts=["Born 1895 in Tervuren"],
        )

        assert task.task_type == "identify"
        assert task.status == "pending"
        assert len(task.known_facts) == 1

    def test_task_with_target(self, sample_person: Person):
        """Test task with target person."""
        task = ResearchTask(
            task_type="extend",
            description="Extend lineage",
            target_person=sample_person,
        )

        assert task.target_person is not None
        assert task.target_person.id == "I001"


class TestGenealogyAssistant:
    """Tests for GenealogyAssistant class."""

    @pytest.fixture
    def mock_anthropic_client(self, mock_anthropic_response):
        """Create mock Anthropic client."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
        return mock_client

    @pytest.mark.asyncio
    async def test_research_basic(self, mock_anthropic_client, mock_anthropic_response):
        """Test basic research query."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            config = AssistantConfig(api_key="test-key")
            assistant = GenealogyAssistant(config)
            await assistant.connect()

            response = await assistant.research("When was Jean Joseph Herinckx born?")

            assert response.message is not None
            assert response.ai_assisted is True
            mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_with_context(self, mock_anthropic_client, mock_anthropic_response):
        """Test research with context."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            config = AssistantConfig(api_key="test-key")
            assistant = GenealogyAssistant(config)
            await assistant.connect()

            context = {"known_facts": ["Born in Belgium", "Emigrated to USA"]}
            response = await assistant.research(
                "What records should I search?",
                context=context,
            )

            assert response.message is not None
            # Context should be included in the call
            call_args = mock_anthropic_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            assert any("Belgium" in str(m) for m in messages)

    @pytest.mark.asyncio
    async def test_parse_confidence_from_response(self, mock_anthropic_client):
        """Test parsing confidence level from response."""
        # Create response with confidence indicator
        mock_content = MagicMock()
        mock_content.text = "Based on the evidence, this conclusion is PROVEN with Confidence: 5"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            response = await assistant.research("Test question")

            assert response.confidence == ConfidenceLevel.GPS_COMPLETE

    @pytest.mark.asyncio
    async def test_parse_next_actions(self, mock_anthropic_client):
        """Test parsing next actions from response."""
        mock_content = MagicMock()
        mock_content.text = """Analysis complete.

## Next Research Actions
- Search Tervuren birth records
- Check FamilySearch Belgium collection
- Contact Rijksarchief Leuven
"""
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            response = await assistant.research("Test question")

            assert len(response.next_actions) >= 1
            assert any("Tervuren" in a for a in response.next_actions)

    @pytest.mark.asyncio
    async def test_reset_conversation(self, mock_anthropic_client, mock_anthropic_response):
        """Test conversation reset."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            # Add some messages
            await assistant.research("Question 1")
            await assistant.research("Question 2")

            assert len(assistant._messages) >= 2

            # Reset
            assistant.reset_conversation()

            assert len(assistant._messages) == 0

    @pytest.mark.asyncio
    async def test_create_research_plan(self, mock_anthropic_client, mock_anthropic_response):
        """Test research plan generation."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            target = Person()
            target.names.append(Name(surname="HERINCKX", given="Jean"))

            response = await assistant.create_research_plan(
                target,
                "Find parents"
            )

            assert response.message is not None

    @pytest.mark.asyncio
    async def test_verify_conclusion(self, mock_anthropic_client, mock_anthropic_response):
        """Test conclusion verification."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            response = await assistant.verify_conclusion(
                "Jean Joseph Herinckx was born 15 March 1895",
                ["Birth certificate from Tervuren", "Census 1900 showing age 5"]
            )

            assert response.message is not None

    @pytest.mark.asyncio
    async def test_generate_archive_letter(self, mock_anthropic_client):
        """Test archive letter generation."""
        mock_content = MagicMock()
        mock_content.text = """Dear Archivist,

I am researching the Herinckx family and would like to request...

Sincerely,
[Researcher]"""
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            assistant = GenealogyAssistant(AssistantConfig(api_key="test"))
            await assistant.connect()

            letter = await assistant.generate_archive_letter(
                archive="Rijksarchief Leuven",
                person_name="Jean Joseph Herinckx",
                records_needed=["Birth certificate 1895"],
                known_facts=["Born in Tervuren"],
            )

            assert "Dear" in letter or "Archivist" in letter
            assert len(letter) > 50

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_anthropic_client, mock_anthropic_response):
        """Test async context manager usage."""
        with patch("genealogy_assistant.api.assistant.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value = mock_anthropic_client

            config = AssistantConfig(api_key="test")

            async with GenealogyAssistant(config) as assistant:
                response = await assistant.research("Test question")
                assert response is not None


class TestSystemPrompt:
    """Tests for GPS system prompt compliance."""

    def test_system_prompt_includes_gps(self):
        """Test that system prompt includes GPS elements."""
        from genealogy_assistant.api.assistant import SYSTEM_PROMPT

        # Must mention GPS
        assert "GPS" in SYSTEM_PROMPT or "Genealogical Proof Standard" in SYSTEM_PROMPT

        # Must mention BCG
        assert "BCG" in SYSTEM_PROMPT or "Board for Certification" in SYSTEM_PROMPT

        # Must mention source hierarchy
        assert "PRIMARY" in SYSTEM_PROMPT or "primary" in SYSTEM_PROMPT.lower()
        assert "SECONDARY" in SYSTEM_PROMPT or "secondary" in SYSTEM_PROMPT.lower()
        assert "TERTIARY" in SYSTEM_PROMPT or "tertiary" in SYSTEM_PROMPT.lower()

    def test_system_prompt_includes_methodology(self):
        """Test system prompt includes research methodology."""
        from genealogy_assistant.api.assistant import SYSTEM_PROMPT

        # Must mention evidence analysis
        assert "evidence" in SYSTEM_PROMPT.lower()

        # Must mention conflict resolution
        assert "conflict" in SYSTEM_PROMPT.lower()

        # Must mention conclusions
        assert "conclusion" in SYSTEM_PROMPT.lower()

    def test_system_prompt_includes_ai_disclosure(self):
        """Test system prompt requires AI disclosure."""
        from genealogy_assistant.api.assistant import SYSTEM_PROMPT

        # Must mention AI assistance disclosure
        assert "AI" in SYSTEM_PROMPT
