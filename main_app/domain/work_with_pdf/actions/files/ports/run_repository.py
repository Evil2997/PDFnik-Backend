from typing import Any, Protocol

RunRow = dict[str, Any]


class RunRepository(Protocol):
    def get(self, run_key: str) -> RunRow | None: ...

    def upsert(self, row: RunRow) -> None: ...

    def list_all(self) -> list[RunRow]: ...
