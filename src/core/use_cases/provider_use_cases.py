"""Use cases for configuring, testing, and selecting verified AI providers."""
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    ProviderConnectionTestResult,
    ProviderSummaryResult,
    SelectProviderModelInput,
    TestProviderConnectionInput,
)
from src.core.entities.provider import (
    CredentialStatus,
    DEFAULT_PROVIDER_BASE_URLS,
    ProviderConfig,
    ProviderConnectionStatus,
    ProviderNotFoundError,
    ProviderType,
    ProviderValidationError,
    build_credential_ref,
    mask_secret,
    redact_secrets,
)
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository


def _to_summary(entity: ProviderConfig) -> ProviderSummaryResult:
    return ProviderSummaryResult(
        id=entity.id,
        name=entity.name,
        provider_type=entity.provider_type,
        base_url=entity.base_url,
        credential_ref=entity.credential_ref,
        credential_preview=entity.credential_preview,
        credential_status=entity.credential_status,
        connection_status=entity.connection_status,
        supported_capabilities=entity.supported_capabilities,
        verified_models=entity.verified_models,
        selected_model=entity.selected_model,
        last_error=entity.last_error,
        last_tested_at=entity.last_tested_at.isoformat() if entity.last_tested_at else None,
        created_at=entity.created_at.isoformat(),
        updated_at=entity.updated_at.isoformat(),
    )


class ConfigureProviderUseCase:
    """Create or update a provider config while isolating secrets in CredentialVaultPort."""

    def __init__(
        self,
        provider_repo: ProviderRepository,
        credential_vault: CredentialVaultPort,
    ) -> None:
        self._provider_repo = provider_repo
        self._credential_vault = credential_vault

    def execute(self, input_data: ConfigureProviderInput) -> ProviderSummaryResult:
        now = datetime.now(timezone.utc)
        existing: Optional[ProviderSummaryResult] = None
        if input_data.provider_id:
            existing = self._provider_repo.get_by_id(input_data.provider_id)
            if existing is None:
                raise ProviderNotFoundError(f"Provider '{input_data.provider_id}' not found.")

        provider_id = existing.id if existing else str(uuid.uuid4())
        resolved_base_url = (
            input_data.base_url
            if input_data.base_url is not None and input_data.base_url.strip()
            else DEFAULT_PROVIDER_BASE_URLS[input_data.provider_type]
        )

        cleaned_secret = input_data.api_key.strip() if input_data.api_key else ""
        if cleaned_secret:
            credential_ref: Optional[str] = build_credential_ref(provider_id)
            self._credential_vault.store_secret(credential_ref, cleaned_secret)
            credential_preview = mask_secret(cleaned_secret)
            credential_status = CredentialStatus.STORED
        elif existing is not None:
            credential_ref = existing.credential_ref
            credential_preview = existing.credential_preview
            if (
                input_data.provider_type == ProviderType.LOCAL_OLLAMA
                and existing.credential_status == CredentialStatus.MISSING
            ):
                credential_status = CredentialStatus.NOT_REQUIRED
            else:
                credential_status = existing.credential_status
        elif input_data.provider_type == ProviderType.LOCAL_OLLAMA:
            credential_ref = None
            credential_preview = None
            credential_status = CredentialStatus.NOT_REQUIRED
        else:
            credential_ref = None
            credential_preview = None
            credential_status = CredentialStatus.MISSING

        if existing is not None:
            endpoint_changed = (
                existing.provider_type != input_data.provider_type
                or existing.base_url != resolved_base_url.strip().rstrip("/")
                or bool(cleaned_secret)
            )
            if endpoint_changed:
                connection_status = ProviderConnectionStatus.UNVERIFIED
                supported_capabilities = ()
                verified_models = ()
                selected_model = input_data.selected_model
                last_error = None
                last_tested_at = None
            else:
                connection_status = existing.connection_status
                supported_capabilities = existing.supported_capabilities
                verified_models = existing.verified_models
                selected_model = (
                    input_data.selected_model
                    if input_data.selected_model is not None
                    else existing.selected_model
                )
                last_error = existing.last_error
                last_tested_at = (
                    datetime.fromisoformat(existing.last_tested_at)
                    if existing.last_tested_at
                    else None
                )
            created_at = datetime.fromisoformat(existing.created_at)
        else:
            connection_status = ProviderConnectionStatus.UNVERIFIED
            supported_capabilities = ()
            verified_models = ()
            selected_model = input_data.selected_model
            last_error = None
            last_tested_at = None
            created_at = now

        entity = ProviderConfig(
            id=provider_id,
            name=input_data.name,
            provider_type=input_data.provider_type,
            base_url=resolved_base_url,
            credential_ref=credential_ref,
            credential_preview=credential_preview,
            credential_status=credential_status,
            connection_status=connection_status,
            supported_capabilities=supported_capabilities,
            verified_models=verified_models,
            selected_model=selected_model,
            last_error=last_error,
            last_tested_at=last_tested_at,
            created_at=created_at,
            updated_at=now,
        )
        summary = _to_summary(entity)
        self._provider_repo.save(summary)
        return summary


class ListProvidersUseCase:
    """List all configured providers without exposing secrets."""

    def __init__(self, provider_repo: ProviderRepository) -> None:
        self._provider_repo = provider_repo

    def execute(self) -> List[ProviderSummaryResult]:
        return self._provider_repo.list_all()


class GetProviderUseCase:
    """Retrieve a configured provider summary by ID."""

    def __init__(self, provider_repo: ProviderRepository) -> None:
        self._provider_repo = provider_repo

    def execute(self, provider_id: str) -> Optional[ProviderSummaryResult]:
        return self._provider_repo.get_by_id(provider_id)


class DeleteProviderUseCase:
    """Delete a provider configuration and purge any associated secret from the vault."""

    def __init__(
        self,
        provider_repo: ProviderRepository,
        credential_vault: CredentialVaultPort,
    ) -> None:
        self._provider_repo = provider_repo
        self._credential_vault = credential_vault

    def execute(self, provider_id: str) -> bool:
        existing = self._provider_repo.get_by_id(provider_id)
        if existing is None:
            return False
        if existing.credential_ref:
            self._credential_vault.delete_secret(existing.credential_ref)
        return self._provider_repo.delete(provider_id)


class TestProviderConnectionUseCase:
    """Verify a provider connection via ProviderGateway and persist verified capabilities."""

    __test__ = False

    def __init__(
        self,
        provider_repo: ProviderRepository,
        credential_vault: CredentialVaultPort,
        provider_gateway: ProviderGateway,
    ) -> None:
        self._provider_repo = provider_repo
        self._credential_vault = credential_vault
        self._provider_gateway = provider_gateway

    def execute(self, input_data: TestProviderConnectionInput) -> ProviderConnectionTestResult:
        provider = self._provider_repo.get_by_id(input_data.provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{input_data.provider_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()
        api_key: Optional[str] = None
        if provider.credential_ref:
            api_key = self._credential_vault.get_secret(provider.credential_ref)

        requires_key = provider.provider_type != ProviderType.LOCAL_OLLAMA
        if requires_key and not api_key:
            message = "Missing API credential in protected storage."
            updated = ProviderSummaryResult(
                id=provider.id,
                name=provider.name,
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                credential_ref=provider.credential_ref,
                credential_preview=None,
                credential_status=CredentialStatus.MISSING,
                connection_status=ProviderConnectionStatus.FAILED,
                supported_capabilities=(),
                verified_models=(),
                selected_model=provider.selected_model,
                last_error=message,
                last_tested_at=now_iso,
                created_at=provider.created_at,
                updated_at=now_iso,
            )
            self._provider_repo.save(updated)
            return ProviderConnectionTestResult(
                provider_id=provider.id,
                success=False,
                connection_status=ProviderConnectionStatus.FAILED,
                supported_capabilities=(),
                verified_models=(),
                selected_model=provider.selected_model,
                message=message,
                tested_at=now_iso,
            )

        try:
            probe = self._provider_gateway.test_connection(
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                api_key=api_key,
            )
            safe_message = redact_secrets(probe.message, [api_key]) or ""
            success = probe.success
            capabilities = probe.supported_capabilities if success else ()
            models = probe.verified_models if success else ()
        except Exception as exc:
            safe_message = redact_secrets(str(exc), [api_key]) or "Provider connection test failed."
            success = False
            capabilities = ()
            models = ()

        if success:
            selected_model = provider.selected_model
            if selected_model and models and selected_model not in models:
                selected_model = models[0]
            elif not selected_model and models:
                selected_model = models[0]
            status = ProviderConnectionStatus.VERIFIED
            last_error = None
        else:
            selected_model = provider.selected_model
            status = ProviderConnectionStatus.FAILED
            last_error = safe_message

        updated = ProviderSummaryResult(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            credential_ref=provider.credential_ref,
            credential_preview=provider.credential_preview,
            credential_status=provider.credential_status,
            connection_status=status,
            supported_capabilities=capabilities,
            verified_models=models,
            selected_model=selected_model,
            last_error=last_error,
            last_tested_at=now_iso,
            created_at=provider.created_at,
            updated_at=now_iso,
        )
        self._provider_repo.save(updated)
        return ProviderConnectionTestResult(
            provider_id=provider.id,
            success=success,
            connection_status=status,
            supported_capabilities=capabilities,
            verified_models=models,
            selected_model=selected_model,
            message=safe_message,
            tested_at=now_iso,
        )


class SelectProviderModelUseCase:
    """Select a verified model on a verified provider."""

    def __init__(self, provider_repo: ProviderRepository) -> None:
        self._provider_repo = provider_repo

    def execute(self, input_data: SelectProviderModelInput) -> ProviderSummaryResult:
        provider = self._provider_repo.get_by_id(input_data.provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{input_data.provider_id}' not found.")
        if provider.connection_status != ProviderConnectionStatus.VERIFIED:
            raise ProviderValidationError("Provider connection must be verified before selecting a model.")
        cleaned_model = input_data.model.strip()
        if not cleaned_model or cleaned_model not in provider.verified_models:
            raise ProviderValidationError(
                f"Model '{cleaned_model}' is not in verified models for provider '{provider.name}'."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        updated = ProviderSummaryResult(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            credential_ref=provider.credential_ref,
            credential_preview=provider.credential_preview,
            credential_status=provider.credential_status,
            connection_status=provider.connection_status,
            supported_capabilities=provider.supported_capabilities,
            verified_models=provider.verified_models,
            selected_model=cleaned_model,
            last_error=provider.last_error,
            last_tested_at=provider.last_tested_at,
            created_at=provider.created_at,
            updated_at=now_iso,
        )
        self._provider_repo.save(updated)
        return updated
