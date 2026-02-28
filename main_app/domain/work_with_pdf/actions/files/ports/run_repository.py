from typing import Any, Optional, Protocol

RunRow = dict[str, Any]


class RunRepository(Protocol):
    def get(self, run_key: str) -> Optional[RunRow]:
        ...

    def upsert(self, row: RunRow) -> None:
        ...

    def list_all(self) -> list[RunRow]:
        ...
