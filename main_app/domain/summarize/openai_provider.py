import openai

from main_app.core.logger import logger
from main_app.domain.summarize.base import SUMMARY_PROMPT

_MODEL = "gpt-4o-mini"
_MAX_TOKENS = 256


class OpenAISummaryProvider:
    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def summarize(self, text: str, prompt: str | None = None) -> str:
        try:
            content = (prompt or SUMMARY_PROMPT).format(text=text)
            resp = await self._client.chat.completions.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": content}],
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("OpenAISummaryProvider failed: %s", exc)
            return ""
