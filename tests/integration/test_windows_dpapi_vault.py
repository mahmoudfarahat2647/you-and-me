"""Integration tests for real Windows DPAPI credential storage and zero-secret persistence."""
import logging
import sys

import httpx
import pytest

from src.adapters.providers.http_provider_gateway import HttpProviderGateway
from src.adapters.security.windows_dpapi_vault import VaultProtectionError, WindowsDpapiVault
from src.adapters.storage.sqlite_provider_repository import SQLiteProviderRepository
from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    TestProviderConnectionInput,
)
from src.core.entities.provider import ProviderType
from src.core.use_cases.provider_use_cases import (
    ConfigureProviderUseCase,
    GetProviderUseCase,
    TestProviderConnectionUseCase,
)


pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows DPAPI integration tests require win32.",
)


def test_real_windows_dpapi_encrypt_reload_decrypt_roundtrip(tmp_path) -> None:
    vault_file = tmp_path / "secrets.vault.json"
    secret_1 = "AIzaSyRealDpapiSecretValue-987654"
    secret_2 = "sk-live-secondary-token-112233"

    vault_1 = WindowsDpapiVault(vault_path=vault_file)
    vault_1.store_secret("provider:p1", secret_1)
    vault_1.store_secret("provider:p2", secret_2)

    raw_vault_disk = vault_file.read_text(encoding="utf-8")
    assert secret_1 not in raw_vault_disk
    assert secret_2 not in raw_vault_disk
    assert "987654" not in raw_vault_disk

    # Reopen a fresh vault instance (simulates app restart)
    vault_2 = WindowsDpapiVault(vault_path=vault_file)
    assert vault_2.has_secret("provider:p1") is True
    assert vault_2.get_secret("provider:p1") == secret_1
    assert vault_2.get_secret("provider:p2") == secret_2

    assert vault_2.delete_secret("provider:p1") is True
    assert vault_2.has_secret("provider:p1") is False
    assert vault_2.get_secret("provider:p1") is None


def test_corrupted_dpapi_blob_raises_without_exposing_secret(tmp_path) -> None:
    vault_file = tmp_path / "corrupt.vault.json"
    vault = WindowsDpapiVault(vault_path=vault_file)
    secret = "sk-super-secret-value-5555"
    vault.store_secret("provider:bad", secret)

    # Corrupt encrypted payload on disk
    content = vault_file.read_text(encoding="utf-8")
    vault_file.write_text(content.replace("A", "B"), encoding="utf-8")

    reopened = WindowsDpapiVault(vault_path=vault_file)
    with pytest.raises(VaultProtectionError) as exc_info:
        reopened.get_secret("provider:bad")
    assert secret not in str(exc_info.value)


def test_zero_plaintext_secrets_in_sqlite_logs_or_dtos_after_reopen(tmp_path, caplog) -> None:
    db_file = tmp_path / "studio.db"
    vault_file = tmp_path / "secrets.vault.json"
    secret = "AIzaSyNeverLeakIntoSqliteOrLogs4567"

    repo_1 = SQLiteProviderRepository(db_path=db_file)
    vault_1 = WindowsDpapiVault(vault_path=vault_file)

    with caplog.at_level(logging.DEBUG):
        created = ConfigureProviderUseCase(repo_1, vault_1).execute(
            ConfigureProviderInput(
                name="Gemini Production",
                provider_type=ProviderType.GEMINI,
                api_key=secret,
            )
        )

    assert created.credential_preview == "••••4567"
    assert secret not in repr(created)

    # Simulate app restart with fresh SQLite + DPAPI vault instances
    repo_2 = SQLiteProviderRepository(db_path=db_file)
    vault_2 = WindowsDpapiVault(vault_path=vault_file)

    def _mock_gemini(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-goog-api-key") == secret
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        )

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_mock_gemini))
    with caplog.at_level(logging.DEBUG):
        test_result = TestProviderConnectionUseCase(repo_2, vault_2, gateway).execute(
            TestProviderConnectionInput(provider_id=created.id)
        )

    assert test_result.success is True
    assert test_result.verified_models == ("gemini-2.5-flash",)

    reloaded = GetProviderUseCase(repo_2).execute(created.id)
    assert reloaded is not None
    assert reloaded.credential_preview == "••••4567"
    assert secret not in repr(reloaded)
    assert secret not in repr(test_result)

    # Inspect raw SQLite database bytes & logs to guarantee zero secret leakage
    raw_db_bytes = db_file.read_bytes()
    assert secret.encode("utf-8") not in raw_db_bytes
    for record in caplog.records:
        assert secret not in record.getMessage()
