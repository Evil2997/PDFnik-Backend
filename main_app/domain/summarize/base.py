from typing import Protocol, runtime_checkable

SUMMARY_PROMPT = (
    "Summarize the following transcript in 2-4 sentences in the same language as the transcript. "
    "Output only the summary, no preamble.\n\n{text}"
)


@runtime_checkable
class SummaryProvider(Protocol):
    async def summarize(self, text: str) -> str: ...
