"""Unit tests for provider configuration, credential masking, and HTTP gateway transport."""
import json
import os

import httpx
import pytest

from src.adapters.providers.http_provider_gateway import HttpProviderGateway
from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    ProviderOperationRequest,
    SelectProviderModelInput,
    TestProviderConnectionInput,
)
from src.core.entities.budget import ExternalJobStatus
from src.core.entities.provider import (
    CredentialStatus,
    ProviderCapability,
    ProviderConnectionStatus,
    ProviderType,
    ProviderValidationError,
    mask_secret,
)
from src.core.use_cases.provider_use_cases import (
    ConfigureProviderUseCase,
    DeleteProviderUseCase,
    SelectProviderModelUseCase,
    TestProviderConnectionUseCase,
)
from tests.unit.test_budget_guard import (
    InMemoryCredentialVault,
    InMemoryProviderRepository,
)


def test_configure_provider_isolates_secret_and_exposes_only_masked_preview() -> None:
    repo = InMemoryProviderRepository()
    vault = InMemoryCredentialVault()
    secret = "AIzaSyVerySensitiveSecret9988"

    summary = ConfigureProviderUseCase(repo, vault).execute(
        ConfigureProviderInput(
            name="  My Gemini  ",
            provider_type=ProviderType.GEMINI,
            api_key=secret,
        )
    )

    assert summary.name == "My Gemini"
    assert summary.credential_status == CredentialStatus.STORED
    assert summary.credential_preview == "••••9988"
    assert summary.credential_ref == f"provider:{summary.id}"
    assert secret not in repr(summary)
    assert vault.get_secret(summary.credential_ref) == secret
    assert mask_secret("abc") == "••••"
    assert mask_secret("  ") is None


def test_gemini_connection_test_uses_header_and_discovers_capabilities() -> None:
    repo = InMemoryProviderRepository()
    vault = InMemoryCredentialVault()
    secret = "AIzaSyGeminiHeaderKey4321"
    captured_urls = []
    captured_headers = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.5-pro-preview-tts",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/veo-2.0-generate-001",
                        "supportedGenerationMethods": ["predictLongRunning"],
                    },
                ]
            },
        )

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_handler))
    configured = ConfigureProviderUseCase(repo, vault).execute(
        ConfigureProviderInput(
            name="Gemini Studio",
            provider_type=ProviderType.GEMINI,
            api_key=secret,
        )
    )

    result = TestProviderConnectionUseCase(repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=configured.id)
    )

    assert result.success is True
    assert result.connection_status == ProviderConnectionStatus.VERIFIED
    assert result.supported_capabilities == (
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.RESEARCH,
        ProviderCapability.TTS,
        ProviderCapability.VIDEO_GENERATION,
    )
    assert result.verified_models == (
        "gemini-2.5-flash",
        "gemini-2.5-pro-preview-tts",
        "veo-2.0-generate-001",
    )
    assert result.selected_model == "gemini-2.5-flash"
    # API key must travel in header, never query string
    assert secret not in captured_urls[0]
    assert captured_headers.get("x-goog-api-key") == secret

    # Selecting another verified model works; unverified model fails
    updated = SelectProviderModelUseCase(repo).execute(
        SelectProviderModelInput(provider_id=configured.id, model="veo-2.0-generate-001")
    )
    assert updated.selected_model == "veo-2.0-generate-001"
    with pytest.raises(ProviderValidationError):
        SelectProviderModelUseCase(repo).execute(
            SelectProviderModelInput(provider_id=configured.id, model="nonexistent-model")
        )


def test_openai_compatible_and_local_ollama_connection_tests_and_redaction() -> None:
    repo = InMemoryProviderRepository()
    vault = InMemoryCredentialVault()
    secret = "sk-proj-secret-token-7777"

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.example.test":
            return httpx.Response(
                401,
                text=f"Unauthorized for Bearer {secret} at ?key={secret}",
            )
        if request.url.host == "127.0.0.1" and request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:14b"}]},
            )
        return httpx.Response(404)

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_handler))

    # Failed OpenAI-compatible connection redacts secret from persisted last_error and return DTO
    bad_provider = ConfigureProviderUseCase(repo, vault).execute(
        ConfigureProviderInput(
            name="Remote OpenAI",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            base_url="https://api.example.test/v1",
            api_key=secret,
        )
    )
    failed = TestProviderConnectionUseCase(repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=bad_provider.id)
    )
    assert failed.success is False
    assert failed.connection_status == ProviderConnectionStatus.FAILED
    assert secret not in failed.message
    stored_bad = repo.get_by_id(bad_provider.id)
    assert stored_bad is not None
    assert stored_bad.last_error is not None
    assert secret not in stored_bad.last_error

    # Local Ollama requires no secret and discovers local models
    ollama = ConfigureProviderUseCase(repo, vault).execute(
        ConfigureProviderInput(
            name="Local Ollama",
            provider_type=ProviderType.LOCAL_OLLAMA,
        )
    )
    assert ollama.credential_status == CredentialStatus.NOT_REQUIRED
    ok = TestProviderConnectionUseCase(repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=ollama.id)
    )
    assert ok.success is True
    assert ok.verified_models == ("llama3.2:latest", "qwen2.5:14b")
    assert ok.supported_capabilities == (
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.RESEARCH,
    )

    # Deleting provider also purges credential from vault
    assert DeleteProviderUseCase(repo, vault).execute(bad_provider.id) is True
    assert bad_provider.credential_ref is not None
    assert vault.has_secret(bad_provider.credential_ref) is False


def test_http_gateway_tracks_external_job_id_and_polls_async_operation() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith(":predictLongRunning"):
            assert request.headers.get("x-request-key") == "req-video-1"
            return httpx.Response(
                200,
                json={"name": "operations/veo-op-555", "done": False},
            )
        if request.method == "GET" and request.url.path == "/v1beta/operations/veo-op-555":
            return httpx.Response(
                200,
                json={"name": "operations/veo-op-555", "done": True, "cost_usd": 1.2},
            )
        return httpx.Response(503, text="Upstream temporary outage")

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_handler))

    submit_res = gateway.submit_operation(
        ProviderOperationRequest(
            provider_id="prov-1",
            provider_type=ProviderType.GEMINI,
            base_url="https://generativelanguage.googleapis.com",
            capability=ProviderCapability.VIDEO_GENERATION,
            model="veo-2.0-generate-001",
            payload={"instances": [{"prompt": "Desert sunrise"}]},
            request_key="req-video-1",
            api_key="AIzaSySecret1234",
        )
    )
    assert submit_res.accepted is True
    assert submit_res.status == ExternalJobStatus.SUBMITTED
    assert submit_res.external_job_id == "operations/veo-op-555"

    poll_res = gateway.poll_operation(
        provider_type=ProviderType.GEMINI,
        base_url="https://generativelanguage.googleapis.com",
        api_key="AIzaSySecret1234",
        external_job_id="operations/veo-op-555",
    )
    assert poll_res.accepted is True
    assert poll_res.status == ExternalJobStatus.SUCCEEDED
    assert poll_res.reported_cost_usd == 1.2


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="Optional live provider test skipped because GEMINI_API_KEY is not set.",
)
def test_optional_live_gemini_connection() -> None:
    gateway = HttpProviderGateway()
    probe = gateway.test_connection(
        provider_type=ProviderType.GEMINI,
        base_url="https://generativelanguage.googleapis.com",
        api_key=os.environ["GEMINI_API_KEY"],
    )
    assert probe.success is True
    assert len(probe.verified_models) > 0
