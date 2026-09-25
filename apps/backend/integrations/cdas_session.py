from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CdasSharedSession:
    """Serializable CDAS authentication state shared across backend workers."""

    token: str
    cookies: dict[str, str]
    obtained_at: datetime
    last_used_at: datetime


class CdasSessionBroker(Protocol):
    """Cross-process session coordination contract used by the CDAS client."""

    async def load(self) -> CdasSharedSession | None: ...

    async def save(self, session: CdasSharedSession) -> None: ...

    async def clear(self) -> None: ...

    def login_lock(self) -> AbstractAsyncContextManager[None]: ...
