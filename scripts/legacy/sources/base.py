"""Source interface.

A Source knows how to talk to one board / listing / aggregator and yield
`Job` objects. Errors on a single source should not kill the run: raise a
`SourceError` with context and the orchestrator will log and continue.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from ..models import Job


class SourceError(Exception):
    pass


class Source(ABC):
    name: str = "base"

    def __init__(self, config: dict) -> None:
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> Iterable[Job]:
        """Yield Job objects. May be a generator."""
        raise NotImplementedError
