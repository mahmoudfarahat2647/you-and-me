"""Port interface for executing real provider connection probes and operations."""
from abc import ABC, abstractmethod
from typing import Optional

from src.core.dto.provider_dto import (
    GatewayConnectionProbeResult,
    ProviderOperationRequest,
    ProviderOperationResponse,
)
from src.core.entities.provider import ProviderType


class ProviderGateway(ABC):
    """Abstract port for communicating with external or local AI provider endpoints."""

    @abstractmethod
    def test_connection(
        self,
        provider_type: ProviderType,
        base_url: str,
        api_key: Optional[str],
    ) -> GatewayConnectionProbeResult:
        """Probe the provider endpoint, verify credentials, and return capabilities/models."""

    @abstractmethod
    def submit_operation(
        self,
        request: ProviderOperationRequest,
    ) -> ProviderOperationResponse:
        """Submit an operation and return normalized status, external job ID, and spend info."""

    @abstractmethod
    def poll_operation(
        self,
        provider_type: ProviderType,
        base_url: str,
        api_key: Optional[str],
        external_job_id: str,
    ) -> ProviderOperationResponse:
        """Poll an existing external job/operation to reconcile uncertain or async outcomes."""
