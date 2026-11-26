"""Port interface for OS-protected secret credential storage."""
from abc import ABC, abstractmethod
from typing import Optional


class CredentialVaultPort(ABC):
    """Abstract port for persisting and retrieving protected secrets outside SQLite."""

    @abstractmethod
    def store_secret(self, credential_ref: str, secret: str) -> None:
        """Encrypt and persist a secret under an opaque credential reference."""

    @abstractmethod
    def get_secret(self, credential_ref: str) -> Optional[str]:
        """Retrieve and decrypt a secret by its credential reference, or None if absent."""

    @abstractmethod
    def delete_secret(self, credential_ref: str) -> bool:
        """Remove a stored secret by its credential reference."""

    @abstractmethod
    def has_secret(self, credential_ref: str) -> bool:
        """Return True if a secret exists for the given credential reference."""
