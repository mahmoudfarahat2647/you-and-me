"""Core domain entities for project budget tracking, spend reservations, and external jobs."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


BUDGET_EPSILON = 1e-9


class BudgetValidationError(Exception):
    """Raised when budget or spend inputs violate domain invariants."""


class BudgetConcurrencyError(Exception):
    """Raised when an atomic budget or idempotency state transition fails."""


class BudgetPolicyDecision(str, Enum):
    """Structured outcome of preflight spend and idempotency evaluation."""

    APPROVED = "approved"
    PAUSE_UNKNOWN_COST = "pause_unknown_cost"
    PAUSE_BUDGET_EXCEEDED = "pause_budget_exceeded"
    BLOCKED_MAX_RETRIES = "blocked_max_retries"
    DUPLICATE_IN_FLIGHT = "duplicate_in_flight"
    ALREADY_COMPLETED = "already_completed"
    PAUSE_UNCERTAIN_OUTCOME = "pause_uncertain_outcome"


class ReservationStatus(str, Enum):
    """Lifecycle status of a spend reservation."""

    ACTIVE = "active"
    SETTLED = "settled"
    RELEASED = "released"
    UNCERTAIN = "uncertain"


class ExternalJobStatus(str, Enum):
    """Lifecycle status of an external provider request/job."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


def round_usd(amount: float) -> float:
    """Round USD amounts to micro-dollar precision to avoid binary float drift."""
    return round(float(amount), 6)


@dataclass
class ProjectBudget:
    """Domain entity representing a project's spending cap and current ledger totals."""

    project_id: str
    budget_limit_usd: float
    spent_usd: float
    reserved_usd: float
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.project_id or not self.project_id.strip():
            raise BudgetValidationError("Project ID cannot be empty.")
        if self.budget_limit_usd < 0:
            raise BudgetValidationError("Project budget limit cannot be negative.")
        if self.spent_usd < 0:
            raise BudgetValidationError("Project spent amount cannot be negative.")
        if self.reserved_usd < 0:
            raise BudgetValidationError("Project reserved amount cannot be negative.")
        self.project_id = self.project_id.strip()
        self.budget_limit_usd = round_usd(self.budget_limit_usd)
        self.spent_usd = round_usd(self.spent_usd)
        self.reserved_usd = round_usd(self.reserved_usd)

    @property
    def remaining_budget_usd(self) -> float:
        """Remaining unspent project budget before accounting for active reservations."""
        return max(0.0, round_usd(self.budget_limit_usd - self.spent_usd))

    @property
    def available_budget_usd(self) -> float:
        """Remaining project budget after deducting both spent and outstanding reservations."""
        return max(0.0, round_usd(self.budget_limit_usd - self.spent_usd - self.reserved_usd))

    def would_exceed(self, estimated_cost_usd: float) -> bool:
        """Return True if estimated_cost + outstanding_reservations > remaining_budget."""
        if estimated_cost_usd < 0:
            raise BudgetValidationError("Estimated cost cannot be negative.")
        projected_commit = round_usd(estimated_cost_usd + self.reserved_usd)
        return projected_commit > (self.remaining_budget_usd + BUDGET_EPSILON)
