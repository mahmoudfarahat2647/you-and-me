"""Core domain entities and security redaction helpers for providers."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Optional, Sequence, Tuple


class ProviderValidationError(Exception):
    """Raised when provider domain validation fails."""


class ProviderNotFoundError(Exception):
    """Raised when a requested provider configuration does not exist."""


class CredentialNotFoundError(Exception):
    """Raised when an expected credential reference is missing from the vault."""


class ProviderType(str, Enum):
    """Supported provider integration types."""

    GEMINI = "gemini"
    OPENAI_COMPATIBLE = "openai_compatible"
    LOCAL_OLLAMA = "local_ollama"


class ProviderCapability(str, Enum):
    """Capabilities a provider/model can expose to workflow stages."""

    TEXT_GENERATION = "text_generation"
    RESEARCH = "research"
    TTS = "tts"
    VIDEO_GENERATION = "video_generation"


class ProviderConnectionStatus(str, Enum):
    """Verification status of a provider configuration."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"


class CredentialStatus(str, Enum):
    """Availability state of a provider credential in protected storage."""

    MISSING = "missing"
    STORED = "stored"
    NOT_REQUIRED = "not_required"


DEFAULT_PROVIDER_BASE_URLS = {
    ProviderType.GEMINI: "https://generativelanguage.googleapis.com",
    ProviderType.OPENAI_COMPATIBLE: "https://api.openai.com/v1",
    ProviderType.LOCAL_OLLAMA: "http://127.0.0.1:11434",
}

_SENSITIVE_QUERY_RE = re.compile(r"([?&](?:key|api_key|token|access_token)=)([^&\s]+)", re.IGNORECASE)
_BEARER_RE = re.compile(r"(Bearer\s+)([A-Za-z0-9._\-+/=]+)", re.IGNORECASE)


def mask_secret(secret: Optional[str]) -> Optional[str]:
    """Return a non-reversible masked preview (e.g. '••••1234') or None."""
    if secret is None:
        return None
    cleaned = secret.strip()
    if not cleaned:
        return None
    if len(cleaned) <= 4:
        return "••••"
    return f"••••{cleaned[-4:]}"


def redact_secrets(text: Optional[str], secrets: Sequence[Optional[str]] = ()) -> Optional[str]:
    """Strip any known secret strings and auth headers/query keys from error text."""
    if text is None:
        return None
    sanitized = str(text)
    for secret in secrets:
        if secret:
            cleaned = secret.strip()
            if len(cleaned) >= 4 and cleaned in sanitized:
                sanitized = sanitized.replace(cleaned, "[REDACTED]")
    sanitized = _SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", sanitized)
    sanitized = _BEARER_RE.sub(r"\1[REDACTED]", sanitized)
    return sanitized


def build_credential_ref(provider_id: str) -> str:
    """Build an opaque credential reference key for vault lookup."""
    cleaned = provider_id.strip()
    if not cleaned:
        raise ProviderValidationError("Provider ID cannot be empty when building credential_ref.")
    return f"provider:{cleaned}"


@dataclass
class ProviderConfig:
    """Provider configuration entity. Secrets are never stored on this entity."""

    id: str
    name: str
    provider_type: ProviderType
    base_url: str
    credential_ref: Optional[str]
    credential_preview: Optional[str]
    credential_status: CredentialStatus
    connection_status: ProviderConnectionStatus
    supported_capabilities: Tuple[ProviderCapability, ...]
    verified_models: Tuple[str, ...]
    selected_model: Optional[str]
    last_error: Optional[str]
    last_tested_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ProviderValidationError("Provider ID cannot be empty.")
        if not self.name or not self.name.strip():
            raise ProviderValidationError("Provider name cannot be empty.")
        if not self.base_url or not self.base_url.strip():
            raise ProviderValidationError("Provider base URL cannot be empty.")

        self.id = self.id.strip()
        self.name = self.name.strip()
        self.base_url = self.base_url.strip().rstrip("/")

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ProviderValidationError("Provider base URL must start with http:// or https://.")

        if self.credential_preview is not None and not self.credential_preview.startswith("••••"):
            raise ProviderValidationError("Credential preview must be masked.")
        if self.selected_model is not None:
            stripped_model = self.selected_model.strip()
            self.selected_model = stripped_model or None
        if self.last_error is not None:
            self.last_error = redact_secrets(self.last_error)
