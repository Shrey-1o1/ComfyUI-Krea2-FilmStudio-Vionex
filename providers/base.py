"""Provider contract for application-style One Node packages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExpansionResult:
    graph: dict[str, Any]
    image: list[Any]
    latent: list[Any]
    seed: int


class BaseGenerationProvider(ABC):
    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def expand(self, config: Any, **raw_inputs: Any) -> ExpansionResult:
        raise NotImplementedError
