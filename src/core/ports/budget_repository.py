"""Port interface for atomic project budget, reservation, and external request ledgers."""
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, TypeVar

from src.core.dto.provider_dto import (
    ExternalRequestRecord,
    ProjectBudgetSummary,
    SpendReservationRecord,
)
from src.core.entities.budget import ReservationStatus

T = TypeVar("T")


class BudgetTransaction(ABC):
    """Atomic unit-of-work context exposed inside `BudgetRepository.run_atomic`."""

    @abstractmethod
    def get_budget_snapshot(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        """Read current budget, spent total, and sum of outstanding reservations."""

    @abstractmethod
    def upsert_budget(
        self,
        project_id: str,
        budget_limit_usd: float,
        updated_at: str,
    ) -> ProjectBudgetSummary:
        """Create or update a project's spending cap while preserving spent/reserved totals."""

    @abstractmethod
    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        """Look up an external request by its unique idempotency key."""

    @abstractmethod
    def get_reservation_by_key(self, request_key: str) -> Optional[SpendReservationRecord]:
        """Look up a spend reservation by its unique idempotency key."""

    @abstractmethod
    def list_requests_for_stage(self, stage_run_id: str) -> List[ExternalRequestRecord]:
        """List all recorded external requests belonging to a stage run."""

    @abstractmethod
    def create_reservation_and_request(
        self,
        reservation: SpendReservationRecord,
        request: ExternalRequestRecord,
    ) -> None:
        """Atomically persist a new spend reservation and pending external request."""

    @abstractmethod
    def update_request_and_reservation(
        self,
        request: ExternalRequestRecord,
        reservation_status: ReservationStatus,
        settled_usd: Optional[float],
        delta_spent_usd: float,
        now_iso: str,
    ) -> ProjectBudgetSummary:
        """Atomically update external request status, reservation state, and project spent total."""


class BudgetRepository(ABC):
    """Abstract port for persisting and locking project budgets and external spend ledgers."""

    @abstractmethod
    def run_atomic(self, fn: Callable[[BudgetTransaction], T]) -> T:
        """Execute `fn` under an exclusive atomic lock/transaction."""

    @abstractmethod
    def get_budget_summary(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        """Return the current budget summary for a project, or None if not configured."""

    @abstractmethod
    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        """Return an external request record by its unique idempotency key."""

    @abstractmethod
    def list_requests_by_project(self, project_id: str) -> List[ExternalRequestRecord]:
        """List external request records for a project ordered by creation time."""

    @abstractmethod
    def list_reservations_by_project(self, project_id: str) -> List[SpendReservationRecord]:
        """List spend reservation records for a project ordered by creation time."""
