import httpx

from main_app.core.logger import logger
from main_app.domain.summarize.base import SUMMARY_PROMPT

_TIMEOUT = 120.0


class OllamaSummaryProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def summarize(self, text: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": SUMMARY_PROMPT.format(text=text),
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                return str(resp.json()["response"]).strip()
        except Exception as exc:
            logger.warning("OllamaSummaryProvider failed: %s", exc)
            return ""
