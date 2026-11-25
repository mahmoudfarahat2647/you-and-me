"""Port interface for channel profile persistence."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.channel_dto import ChannelProfileResult


class ChannelRepository(ABC):
    """Abstract port for persisting and querying channel profiles."""

    @abstractmethod
    def save(self, channel: ChannelProfileResult) -> None:
        """Persist a plain channel profile record."""
        pass

    @abstractmethod
    def get_by_id(self, channel_id: str) -> Optional[ChannelProfileResult]:
        """Retrieve a channel profile by its identifier."""
        pass

    @abstractmethod
    def list_all(self) -> List[ChannelProfileResult]:
        """List all saved channel profiles."""
        pass

    @abstractmethod
    def delete(self, channel_id: str) -> bool:
        """Delete a channel profile by its identifier."""
        pass
