import anthropic
from anthropic.types import TextBlock

from main_app.core.logger import logger
from main_app.domain.summarize.base import SUMMARY_PROMPT

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256


class AnthropicSummaryProvider:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str) -> str:
        try:
            msg = await self._client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": SUMMARY_PROMPT.format(text=text)}],
            )
            block = msg.content[0]
            return block.text.strip() if isinstance(block, TextBlock) else ""
        except Exception as exc:
            logger.warning("AnthropicSummaryProvider failed: %s", exc)
            return ""
