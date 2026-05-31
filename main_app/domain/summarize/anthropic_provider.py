import anthropic

from main_app.core.logger import logger
from main_app.domain.summarize.base import SUMMARY_PROMPT

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256


class AnthropicSummaryProvider:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str, prompt: str | None = None) -> str:
        try:
            content = (prompt or SUMMARY_PROMPT).format(text=text)
            msg = await self._client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": content}],
            )
            block = msg.content[0]
            raw = getattr(block, "text", None)
            return raw.strip() if isinstance(raw, str) else ""
        except Exception as exc:
            logger.warning("AnthropicSummaryProvider failed: %s", exc)
            return ""
