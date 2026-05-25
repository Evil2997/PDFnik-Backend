from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main_app.domain.summarize.anthropic_provider import AnthropicSummaryProvider
from main_app.domain.summarize.factory import get_summary_provider
from main_app.domain.summarize.ollama_provider import OllamaSummaryProvider
from main_app.domain.summarize.openai_provider import OpenAISummaryProvider

# ---------------------------------------------------------------------------
# AnthropicSummaryProvider
# ---------------------------------------------------------------------------


class TestAnthropicSummaryProvider:
    @pytest.mark.asyncio
    async def test_returns_summary_text(self):
        provider = AnthropicSummaryProvider(api_key="test-key")
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="  Nice summary.  ")]

        with patch.object(
            provider._client.messages, "create", new=AsyncMock(return_value=mock_msg)
        ):
            result = await provider.summarize("Long transcript text here.")

        assert result == "Nice summary."

    @pytest.mark.asyncio
    async def test_returns_empty_string_on_exception(self):
        provider = AnthropicSummaryProvider(api_key="test-key")

        with patch.object(
            provider._client.messages,
            "create",
            new=AsyncMock(side_effect=Exception("API error")),
        ):
            result = await provider.summarize("text")

        assert result == ""


# ---------------------------------------------------------------------------
# OpenAISummaryProvider
# ---------------------------------------------------------------------------


class TestOpenAISummaryProvider:
    @pytest.mark.asyncio
    async def test_returns_summary_text(self):
        provider = OpenAISummaryProvider(api_key="test-key")
        mock_choice = MagicMock()
        mock_choice.message.content = "  OpenAI summary.  "
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        with patch.object(
            provider._client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_resp),
        ):
            result = await provider.summarize("Long transcript text here.")

        assert result == "OpenAI summary."

    @pytest.mark.asyncio
    async def test_returns_empty_string_on_exception(self):
        provider = OpenAISummaryProvider(api_key="test-key")

        with patch.object(
            provider._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("API error")),
        ):
            result = await provider.summarize("text")

        assert result == ""


# ---------------------------------------------------------------------------
# OllamaSummaryProvider
# ---------------------------------------------------------------------------


class TestOllamaSummaryProvider:
    @pytest.mark.asyncio
    async def test_returns_summary_text(self):
        provider = OllamaSummaryProvider(base_url="http://localhost:11434", model="llama3.2")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "  Ollama summary.  "}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "main_app.domain.summarize.ollama_provider.httpx.AsyncClient", return_value=mock_client
        ):
            result = await provider.summarize("Long transcript text here.")

        assert result == "Ollama summary."

    @pytest.mark.asyncio
    async def test_returns_empty_string_on_http_error(self):
        provider = OllamaSummaryProvider(base_url="http://localhost:11434", model="llama3.2")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with patch(
            "main_app.domain.summarize.ollama_provider.httpx.AsyncClient", return_value=mock_client
        ):
            result = await provider.summarize("text")

        assert result == ""

    def test_base_url_trailing_slash_stripped(self):
        provider = OllamaSummaryProvider(base_url="http://localhost:11434/", model="llama3.2")
        assert provider._base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestGetSummaryProvider:
    def _settings(self, **kwargs):
        m = MagicMock()
        defaults = {
            "SUMMARY_PROVIDER": "disabled",
            "ANTHROPIC_API_KEY": None,
            "OPENAI_API_KEY": None,
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.2",
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(m, k, v)
        return m

    def test_disabled_returns_none(self):
        assert get_summary_provider(self._settings(SUMMARY_PROVIDER="disabled")) is None

    def test_empty_returns_none(self):
        assert get_summary_provider(self._settings(SUMMARY_PROVIDER="")) is None

    def test_anthropic_no_key_returns_none(self):
        assert (
            get_summary_provider(
                self._settings(SUMMARY_PROVIDER="anthropic", ANTHROPIC_API_KEY=None)
            )
            is None
        )

    def test_anthropic_with_key_returns_provider(self):
        p = get_summary_provider(
            self._settings(SUMMARY_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-123")
        )
        assert isinstance(p, AnthropicSummaryProvider)

    def test_openai_no_key_returns_none(self):
        assert (
            get_summary_provider(self._settings(SUMMARY_PROVIDER="openai", OPENAI_API_KEY=None))
            is None
        )

    def test_openai_with_key_returns_provider(self):
        p = get_summary_provider(self._settings(SUMMARY_PROVIDER="openai", OPENAI_API_KEY="sk-456"))
        assert isinstance(p, OpenAISummaryProvider)

    def test_ollama_returns_provider(self):
        p = get_summary_provider(self._settings(SUMMARY_PROVIDER="ollama"))
        assert isinstance(p, OllamaSummaryProvider)

    def test_unknown_provider_returns_none(self):
        assert get_summary_provider(self._settings(SUMMARY_PROVIDER="cohere")) is None
