"""Pluggable preflight port for budget, quota, or policy checks before stage execution."""
from abc import ABC, abstractmethod
from src.core.dto.workflow_dto import PreflightCheckInput, PreflightDecision


class ExecutionPreflightPort(ABC):
    """Abstract preflight hook evaluated before submitting a stage to StageExecutor."""

    @abstractmethod
    def check(self, request: PreflightCheckInput) -> PreflightDecision:
        """Evaluate whether a stage execution is permitted to proceed."""
        pass


class AllowAllExecutionPreflight(ExecutionPreflightPort):
    """Default no-op preflight implementation that allows all stage executions."""

    def check(self, request: PreflightCheckInput) -> PreflightDecision:
        return PreflightDecision(allowed=True)
