"""Base loader interface."""
from abc import ABC, abstractmethod
from pathlib import Path


class BaseLoader(ABC):
    @abstractmethod
    def load(self, path: Path) -> str:
        """Load file content as text."""
        ...

    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        ...
