from main_app.core.logger import logger
from main_app.domain.summarize.anthropic_provider import AnthropicSummaryProvider
from main_app.domain.summarize.base import SummaryProvider
from main_app.domain.summarize.ollama_provider import OllamaSummaryProvider
from main_app.domain.summarize.openai_provider import OpenAISummaryProvider


def get_summary_provider(settings) -> SummaryProvider | None:
    provider = (getattr(settings, "SUMMARY_PROVIDER", "") or "").lower()

    if not provider or provider == "disabled":
        return None

    if provider == "anthropic":
        key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not key:
            logger.warning("SUMMARY_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set — disabled")
            return None
        return AnthropicSummaryProvider(api_key=key)

    if provider == "openai":
        key = getattr(settings, "OPENAI_API_KEY", None)
        if not key:
            logger.warning("SUMMARY_PROVIDER=openai but OPENAI_API_KEY is not set — disabled")
            return None
        return OpenAISummaryProvider(api_key=key)

    if provider == "ollama":
        return OllamaSummaryProvider(
            base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
            model=getattr(settings, "OLLAMA_MODEL", "llama3.2"),
        )

    logger.warning("Unknown SUMMARY_PROVIDER=%r — disabled", provider)
    return None
