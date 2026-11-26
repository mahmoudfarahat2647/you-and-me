"""API routes for managing AI providers, connection checks, project budgets, and spend ledger."""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    ExternalRequestRecord,
    ProjectBudgetSummary,
    ProviderConnectionTestResult,
    ProviderSummaryResult,
    RecordSpendOutcomeInput,
    SelectProviderModelInput,
    SetProjectBudgetInput,
    SpendPreflightInput,
    SpendPreflightResult,
    SpendReservationRecord,
    TestProviderConnectionInput,
)
from src.core.entities.budget import (
    BudgetValidationError,
    ExternalJobStatus,
)
from src.core.entities.provider import (
    CredentialStatus,
    ProviderCapability,
    ProviderConnectionStatus,
    ProviderNotFoundError,
    ProviderType,
    ProviderValidationError,
)
from src.core.ports.budget_repository import BudgetRepository
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository
from src.core.use_cases.budget_guard import (
    BudgetGuardUseCase,
    ExecuteGuardedProviderCallUseCase,
    GetProjectBudgetUseCase,
    SetProjectBudgetUseCase,
)
from src.core.use_cases.provider_use_cases import (
    ConfigureProviderUseCase,
    DeleteProviderUseCase,
    GetProviderUseCase,
    ListProvidersUseCase,
    SelectProviderModelUseCase,
    TestProviderConnectionUseCase,
)

router = APIRouter(tags=["providers", "budget"])


# ---------------------------------------------------------------------------
# Dependency placeholders (overridden in create_app)
# ---------------------------------------------------------------------------


def get_provider_repository() -> ProviderRepository:
    raise NotImplementedError("Provider repository dependency must be configured.")


def get_credential_vault() -> CredentialVaultPort:
    raise NotImplementedError("Credential vault dependency must be configured.")


def get_provider_gateway() -> ProviderGateway:
    raise NotImplementedError("Provider gateway dependency must be configured.")


def get_budget_repository() -> BudgetRepository:
    raise NotImplementedError("Budget repository dependency must be configured.")


# ---------------------------------------------------------------------------
# Pydantic request / response schemas (secrets NEVER appear in read schemas)
# ---------------------------------------------------------------------------


class ConfigureProviderRequest(BaseModel):
    provider_id: Optional[str] = None
    name: str = Field(..., min_length=1)
    provider_type: ProviderType
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, repr=False)
    selected_model: Optional[str] = None


class SelectModelRequest(BaseModel):
    model: str = Field(..., min_length=1)


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: ProviderType
    base_url: str
    credential_ref: Optional[str] = None
    credential_preview: Optional[str] = None
    credential_status: CredentialStatus
    connection_status: ProviderConnectionStatus
    supported_capabilities: List[ProviderCapability]
    verified_models: List[str]
    selected_model: Optional[str] = None
    last_error: Optional[str] = None
    last_tested_at: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_result(cls, res: ProviderSummaryResult) -> "ProviderResponse":
        return cls(
            id=res.id,
            name=res.name,
            provider_type=res.provider_type,
            base_url=res.base_url,
            credential_ref=res.credential_ref,
            credential_preview=res.credential_preview,
            credential_status=res.credential_status,
            connection_status=res.connection_status,
            supported_capabilities=list(res.supported_capabilities),
            verified_models=list(res.verified_models),
            selected_model=res.selected_model,
            last_error=res.last_error,
            last_tested_at=res.last_tested_at,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )


class ProviderConnectionTestResponse(BaseModel):
    provider_id: str
    success: bool
    connection_status: ProviderConnectionStatus
    supported_capabilities: List[ProviderCapability]
    verified_models: List[str]
    selected_model: Optional[str] = None
    message: str
    tested_at: str

    @classmethod
    def from_result(cls, res: ProviderConnectionTestResult) -> "ProviderConnectionTestResponse":
        return cls(
            provider_id=res.provider_id,
            success=res.success,
            connection_status=res.connection_status,
            supported_capabilities=list(res.supported_capabilities),
            verified_models=list(res.verified_models),
            selected_model=res.selected_model,
            message=res.message,
            tested_at=res.tested_at,
        )


class SetProjectBudgetRequest(BaseModel):
    budget_limit_usd: float = Field(..., ge=0.0)


class ProjectBudgetResponse(BaseModel):
    project_id: str
    budget_limit_usd: float
    spent_usd: float
    outstanding_reservations_usd: float
    remaining_budget_usd: float
    available_budget_usd: float
    currency: str = "USD"
    configured: bool = True
    updated_at: str

    @classmethod
    def from_summary(
        cls, summary: ProjectBudgetSummary, *, configured: bool = True
    ) -> "ProjectBudgetResponse":
        return cls(
            project_id=summary.project_id,
            budget_limit_usd=summary.budget_limit_usd,
            spent_usd=summary.spent_usd,
            outstanding_reservations_usd=summary.outstanding_reservations_usd,
            remaining_budget_usd=summary.remaining_budget_usd,
            available_budget_usd=summary.available_budget_usd,
            currency="USD",
            configured=configured,
            updated_at=summary.updated_at,
        )


class ExternalRequestResponse(BaseModel):
    id: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    operation: ProviderCapability
    model: Optional[str] = None
    external_job_id: Optional[str] = None
    status: ExternalJobStatus
    attempt_number: int
    estimated_cost_usd: Optional[float] = None
    reported_cost_usd: Optional[float] = None
    explicitly_approved: bool
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, rec: ExternalRequestRecord) -> "ExternalRequestResponse":
        return cls(
            id=rec.id,
            project_id=rec.project_id,
            stage_run_id=rec.stage_run_id,
            request_key=rec.request_key,
            provider_id=rec.provider_id,
            operation=rec.operation,
            model=rec.model,
            external_job_id=rec.external_job_id,
            status=rec.status,
            attempt_number=rec.attempt_number,
            estimated_cost_usd=rec.estimated_cost_usd,
            reported_cost_usd=rec.reported_cost_usd,
            explicitly_approved=rec.explicitly_approved,
            error_message=rec.error_message,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )


class SpendReservationResponse(BaseModel):
    id: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    reserved_usd: float
    settled_usd: Optional[float] = None
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, rec: SpendReservationRecord) -> "SpendReservationResponse":
        return cls(
            id=rec.id,
            project_id=rec.project_id,
            stage_run_id=rec.stage_run_id,
            request_key=rec.request_key,
            provider_id=rec.provider_id,
            reserved_usd=rec.reserved_usd,
            settled_usd=rec.settled_usd,
            status=rec.status.value,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )


class ProjectSpendLedgerResponse(BaseModel):
    budget: ProjectBudgetResponse
    reservations: List[SpendReservationResponse]
    requests: List[ExternalRequestResponse]


class SpendPreflightRequest(BaseModel):
    stage_run_id: str = Field(..., min_length=1)
    request_key: str = Field(..., min_length=1)
    provider_id: str = Field(..., min_length=1)
    operation: ProviderCapability = ProviderCapability.TEXT_GENERATION
    estimated_cost_usd: Optional[float] = Field(None, ge=0.0)
    model: Optional[str] = None
    is_retry: bool = False
    max_retries: int = Field(2, ge=0)
    explicit_approval: bool = False
    approved_cost_cap_usd: Optional[float] = Field(None, ge=0.0)


class ApproveSpendRequest(BaseModel):
    stage_run_id: Optional[str] = None
    provider_id: Optional[str] = None
    operation: ProviderCapability = ProviderCapability.TEXT_GENERATION
    estimated_cost_usd: Optional[float] = Field(None, ge=0.0)
    approved_cost_cap_usd: Optional[float] = Field(None, ge=0.0)
    model: Optional[str] = None
    is_retry: bool = False
    max_retries: int = Field(2, ge=0)


class ReconcileSpendRequest(BaseModel):
    status: Optional[ExternalJobStatus] = None
    external_job_id: Optional[str] = None
    reported_cost_usd: Optional[float] = Field(None, ge=0.0)
    error_message: Optional[str] = None


class SpendPreflightResponse(BaseModel):
    allowed: bool
    decision: str
    requires_user_approval: bool
    allows_manual_fallback: bool
    message: str
    project_id: str
    stage_run_id: str
    request_key: str
    provider_id: str
    reservation_id: Optional[str] = None
    external_request_id: Optional[str] = None
    external_job_id: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    reserved_amount_usd: float
    outstanding_reservations_usd: float
    remaining_budget_usd: float
    budget_limit_usd: float
    spent_usd: float
    attempts_used: int
    max_retries: int
    available_actions: List[str]

    @classmethod
    def from_result(cls, res: SpendPreflightResult) -> "SpendPreflightResponse":
        return cls(
            allowed=res.allowed,
            decision=res.decision.value,
            requires_user_approval=res.requires_user_approval,
            allows_manual_fallback=res.allows_manual_fallback,
            message=res.message,
            project_id=res.project_id,
            stage_run_id=res.stage_run_id,
            request_key=res.request_key,
            provider_id=res.provider_id,
            reservation_id=res.reservation_id,
            external_request_id=res.external_request_id,
            external_job_id=res.external_job_id,
            estimated_cost_usd=res.estimated_cost_usd,
            reserved_amount_usd=res.reserved_amount_usd,
            outstanding_reservations_usd=res.outstanding_reservations_usd,
            remaining_budget_usd=res.remaining_budget_usd,
            budget_limit_usd=res.budget_limit_usd,
            spent_usd=res.spent_usd,
            attempts_used=res.attempts_used,
            max_retries=res.max_retries,
            available_actions=list(res.available_actions),
        )


class ReconcileSpendResponse(BaseModel):
    request: ExternalRequestResponse
    budget: ProjectBudgetResponse


def _zero_budget_response(project_id: str) -> ProjectBudgetResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    return ProjectBudgetResponse(
        project_id=project_id,
        budget_limit_usd=0.0,
        spent_usd=0.0,
        outstanding_reservations_usd=0.0,
        remaining_budget_usd=0.0,
        available_budget_usd=0.0,
        currency="USD",
        configured=False,
        updated_at=now_iso,
    )


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=List[ProviderResponse])
def list_providers(
    repo: ProviderRepository = Depends(get_provider_repository),
) -> List[ProviderResponse]:
    results = ListProvidersUseCase(repo).execute()
    return [ProviderResponse.from_result(item) for item in results]


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def configure_provider(
    request: ConfigureProviderRequest,
    repo: ProviderRepository = Depends(get_provider_repository),
    vault: CredentialVaultPort = Depends(get_credential_vault),
) -> ProviderResponse:
    try:
        result = ConfigureProviderUseCase(repo, vault).execute(
            ConfigureProviderInput(
                provider_id=request.provider_id,
                name=request.name,
                provider_type=request.provider_type,
                base_url=request.base_url,
                api_key=request.api_key,
                selected_model=request.selected_model,
            )
        )
        return ProviderResponse.from_result(result)
    except ProviderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ProviderValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
def get_provider(
    provider_id: str,
    repo: ProviderRepository = Depends(get_provider_repository),
) -> ProviderResponse:
    result = GetProviderUseCase(repo).execute(provider_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )
    return ProviderResponse.from_result(result)


@router.post("/providers/{provider_id}/test", response_model=ProviderConnectionTestResponse)
def test_provider_connection(
    provider_id: str,
    repo: ProviderRepository = Depends(get_provider_repository),
    vault: CredentialVaultPort = Depends(get_credential_vault),
    gateway: ProviderGateway = Depends(get_provider_gateway),
) -> ProviderConnectionTestResponse:
    try:
        result = TestProviderConnectionUseCase(repo, vault, gateway).execute(
            TestProviderConnectionInput(provider_id=provider_id)
        )
        return ProviderConnectionTestResponse.from_result(result)
    except ProviderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.put("/providers/{provider_id}/model", response_model=ProviderResponse)
def select_provider_model(
    provider_id: str,
    request: SelectModelRequest,
    repo: ProviderRepository = Depends(get_provider_repository),
) -> ProviderResponse:
    try:
        result = SelectProviderModelUseCase(repo).execute(
            SelectProviderModelInput(provider_id=provider_id, model=request.model)
        )
        return ProviderResponse.from_result(result)
    except ProviderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ProviderValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: str,
    repo: ProviderRepository = Depends(get_provider_repository),
    vault: CredentialVaultPort = Depends(get_credential_vault),
) -> Dict[str, bool]:
    deleted = DeleteProviderUseCase(repo, vault).execute(provider_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Project budget & spend ledger endpoints
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/budget", response_model=ProjectBudgetResponse)
def get_project_budget(
    project_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
) -> ProjectBudgetResponse:
    summary = GetProjectBudgetUseCase(budget_repo).execute(project_id)
    if summary is None:
        return _zero_budget_response(project_id)
    return ProjectBudgetResponse.from_summary(summary, configured=True)


@router.put("/projects/{project_id}/budget", response_model=ProjectBudgetResponse)
def set_project_budget(
    project_id: str,
    request: SetProjectBudgetRequest,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
) -> ProjectBudgetResponse:
    try:
        summary = SetProjectBudgetUseCase(budget_repo).execute(
            SetProjectBudgetInput(
                project_id=project_id,
                budget_limit_usd=request.budget_limit_usd,
            )
        )
        return ProjectBudgetResponse.from_summary(summary, configured=True)
    except BudgetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.get("/projects/{project_id}/spend", response_model=ProjectSpendLedgerResponse)
def get_project_spend_ledger(
    project_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
) -> ProjectSpendLedgerResponse:
    summary = GetProjectBudgetUseCase(budget_repo).execute(project_id)
    budget_resp = (
        ProjectBudgetResponse.from_summary(summary, configured=True)
        if summary is not None
        else _zero_budget_response(project_id)
    )
    reservations = [
        SpendReservationResponse.from_record(r)
        for r in budget_repo.list_reservations_by_project(project_id)
    ]
    requests = [
        ExternalRequestResponse.from_record(r)
        for r in budget_repo.list_requests_by_project(project_id)
    ]
    return ProjectSpendLedgerResponse(
        budget=budget_resp,
        reservations=reservations,
        requests=requests,
    )


@router.post("/projects/{project_id}/spend/preflight", response_model=SpendPreflightResponse)
def evaluate_spend_preflight(
    project_id: str,
    request: SpendPreflightRequest,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
) -> SpendPreflightResponse:
    try:
        result = BudgetGuardUseCase(budget_repo).preflight_and_reserve(
            SpendPreflightInput(
                project_id=project_id,
                stage_run_id=request.stage_run_id,
                request_key=request.request_key,
                provider_id=request.provider_id,
                operation=request.operation,
                estimated_cost_usd=request.estimated_cost_usd,
                model=request.model,
                is_retry=request.is_retry,
                max_retries=request.max_retries,
                explicit_approval=request.explicit_approval,
                approved_cost_cap_usd=request.approved_cost_cap_usd,
            )
        )
        return SpendPreflightResponse.from_result(result)
    except BudgetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.post(
    "/projects/{project_id}/spend/{request_key}/approve",
    response_model=SpendPreflightResponse,
)
def approve_spend_request(
    project_id: str,
    request_key: str,
    request: Optional[ApproveSpendRequest] = None,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
) -> SpendPreflightResponse:
    payload = request or ApproveSpendRequest()
    existing = budget_repo.get_request_by_key(request_key)
    stage_run_id = (
        payload.stage_run_id
        or (existing.stage_run_id if existing else None)
        or f"{project_id}:{request_key}"
    )
    provider_id = (
        payload.provider_id
        or (existing.provider_id if existing else None)
        or "approved-provider"
    )
    operation = existing.operation if existing else payload.operation
    estimated_cost = (
        payload.estimated_cost_usd
        if payload.estimated_cost_usd is not None
        else (existing.estimated_cost_usd if existing else None)
    )
    try:
        result = BudgetGuardUseCase(budget_repo).preflight_and_reserve(
            SpendPreflightInput(
                project_id=project_id,
                stage_run_id=stage_run_id,
                request_key=request_key,
                provider_id=provider_id,
                operation=operation,
                estimated_cost_usd=estimated_cost,
                model=payload.model or (existing.model if existing else None),
                is_retry=payload.is_retry,
                max_retries=payload.max_retries,
                explicit_approval=True,
                approved_cost_cap_usd=payload.approved_cost_cap_usd,
            )
        )
        return SpendPreflightResponse.from_result(result)
    except BudgetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.post(
    "/projects/{project_id}/spend/{request_key}/reconcile",
    response_model=ReconcileSpendResponse,
)
def reconcile_spend_request(
    project_id: str,
    request_key: str,
    request: Optional[ReconcileSpendRequest] = None,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    provider_repo: ProviderRepository = Depends(get_provider_repository),
    vault: CredentialVaultPort = Depends(get_credential_vault),
    gateway: ProviderGateway = Depends(get_provider_gateway),
) -> ReconcileSpendResponse:
    existing = budget_repo.get_request_by_key(request_key)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External request '{request_key}' not found for project '{project_id}'.",
        )

    try:
        if request is not None and request.status is not None:
            updated_req, updated_budget = BudgetGuardUseCase(budget_repo).record_outcome(
                RecordSpendOutcomeInput(
                    request_key=request_key,
                    status=request.status,
                    external_job_id=request.external_job_id,
                    reported_cost_usd=request.reported_cost_usd,
                    error_message=request.error_message,
                )
            )
        else:
            uc = ExecuteGuardedProviderCallUseCase(
                provider_repo=provider_repo,
                credential_vault=vault,
                provider_gateway=gateway,
                budget_repo=budget_repo,
            )
            updated_req, updated_budget = uc.reconcile_request(request_key)
        return ReconcileSpendResponse(
            request=ExternalRequestResponse.from_record(updated_req),
            budget=ProjectBudgetResponse.from_summary(updated_budget, configured=True),
        )
    except ProviderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except BudgetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
