"""Port interface for persisting non-secret provider metadata."""
from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.dto.provider_dto import ProviderSummaryResult


class ProviderRepository(ABC):
    """Abstract port for storing provider configs and verified capabilities (never secrets)."""

    @abstractmethod
    def save(self, provider: ProviderSummaryResult) -> None:
        """Insert or update a provider summary record."""

    @abstractmethod
    def get_by_id(self, provider_id: str) -> Optional[ProviderSummaryResult]:
        """Fetch a provider summary record by ID."""

    @abstractmethod
    def list_all(self) -> List[ProviderSummaryResult]:
        """List all configured providers ordered by most recently updated."""

    @abstractmethod
    def delete(self, provider_id: str) -> bool:
        """Delete a provider summary record by ID."""
