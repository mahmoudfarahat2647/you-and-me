"""Plain frozen boundary DTOs for providers, credentials status, and spend guardrails."""
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Tuple

from src.core.entities.budget import (
    BudgetPolicyDecision,
    ExternalJobStatus,
    ReservationStatus,
)
from src.core.entities.provider import (
    CredentialStatus,
    ProviderCapability,
    ProviderConnectionStatus,
    ProviderType,
)


@dataclass(frozen=True)
class ConfigureProviderInput:
    """Write-only input DTO for creating or updating a provider configuration."""

    name: str
    provider_type: ProviderType
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    selected_model: Optional[str] = None
    provider_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderSummaryResult:
    """Read DTO for provider configuration; never contains plaintext secrets."""

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
    last_tested_at: Optional[str]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TestProviderConnectionInput:
    """Input DTO for triggering a real provider connection check."""

    __test__: ClassVar[bool] = False
    provider_id: str


@dataclass(frozen=True)
class SelectProviderModelInput:
    """Input DTO for choosing a verified model on a provider."""

    provider_id: str
    model: str


@dataclass(frozen=True)
class GatewayConnectionProbeResult:
    """Raw connection verification result returned by ProviderGateway."""

    success: bool
    supported_capabilities: Tuple[ProviderCapability, ...]
    verified_models: Tuple[str, ...]
    message: str
    endpoint_checked: str


@dataclass(frozen=True)
class ProviderConnectionTestResult:
    """Persisted connection test result returned across the application boundary."""

    provider_id: str
    success: bool
    connection_status: ProviderConnectionStatus
    supported_capabilities: Tuple[ProviderCapability, ...]
    verified_models: Tuple[str, ...]
    selected_model: Optional[str]
    message: str
    tested_at: str


@dataclass(frozen=True)
class ProviderOperationRequest:
    """Gateway request DTO. `api_key` is transient in-memory only and never persisted."""

    provider_id: str
    provider_type: ProviderType
    base_url: str
    capability: ProviderCapability
    model: str
    payload: Dict[str, Any]
    request_key: str
    api_key: Optional[str] = None


@dataclass(frozen=True)
class ProviderOperationResponse:
    """Normalized response returned by a ProviderGateway submission or poll."""

    accepted: bool
    external_job_id: Optional[str]
    status: ExternalJobStatus
    output_summary: Optional[str] = None
    reported_cost_usd: Optional[float] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class SetProjectBudgetInput:
    """Input DTO to create or update a project's budget cap."""

    project_id: str
    budget_limit_usd: float


@dataclass(frozen=True)
class ProjectBudgetSummary:
    """Plain read DTO summarizing a project's budget, spend, and reservations."""

    project_id: str
    budget_limit_usd: float
    spent_usd: float
    outstanding_reservations_usd: float
    remaining_budget_usd: float
    available_budget_usd: float
    updated_at: str


@dataclass(frozen=True)
class SpendPreflightInput:
    """Input DTO for evaluating budget and idempotency before a paid provider call."""

    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    operation: ProviderCapability
    estimated_cost_usd: Optional[float]
    model: Optional[str] = None
    is_retry: bool = False
    max_retries: int = 2
    explicit_approval: bool = False
    approved_cost_cap_usd: Optional[float] = None


@dataclass(frozen=True)
class SpendPreflightResult:
    """Structured preflight decision returned before any paid submission."""

    allowed: bool
    decision: BudgetPolicyDecision
    requires_user_approval: bool
    allows_manual_fallback: bool
    message: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    reservation_id: Optional[str]
    external_request_id: Optional[str]
    external_job_id: Optional[str]
    estimated_cost_usd: Optional[float]
    reserved_amount_usd: float
    outstanding_reservations_usd: float
    remaining_budget_usd: float
    budget_limit_usd: float
    spent_usd: float
    attempts_used: int
    max_retries: int
    available_actions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RecordSpendOutcomeInput:
    """Input DTO to settle, fail, or mark uncertain an active external request."""

    request_key: str
    status: ExternalJobStatus
    external_job_id: Optional[str] = None
    reported_cost_usd: Optional[float] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ExternalRequestRecord:
    """Persisted record of an external provider request/job and its spend."""

    id: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    operation: ProviderCapability
    model: Optional[str]
    external_job_id: Optional[str]
    status: ExternalJobStatus
    attempt_number: int
    estimated_cost_usd: Optional[float]
    reported_cost_usd: Optional[float]
    explicitly_approved: bool
    error_message: Optional[str]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SpendReservationRecord:
    """Persisted spend reservation record tied to an idempotent external request."""

    id: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    reserved_usd: float
    settled_usd: Optional[float]
    status: ReservationStatus
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ExecuteGuardedProviderCallInput:
    """Combined input DTO for guarded provider execution with preflight + submission."""

    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    operation: ProviderCapability
    payload: Dict[str, Any]
    estimated_cost_usd: Optional[float]
    model: Optional[str] = None
    is_retry: bool = False
    max_retries: int = 2
    explicit_approval: bool = False
    approved_cost_cap_usd: Optional[float] = None


@dataclass(frozen=True)
class ExecuteGuardedProviderCallResult:
    """Combined result DTO from guarded provider execution."""

    preflight: SpendPreflightResult
    submitted: bool
    response: Optional[ProviderOperationResponse]
    request_record: Optional[ExternalRequestRecord]
    budget_summary: ProjectBudgetSummary
