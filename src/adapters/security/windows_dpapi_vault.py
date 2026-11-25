"""Windows DPAPI protected storage adapter implementing CredentialVaultPort."""
from abc import ABC, abstractmethod
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import threading
from typing import Dict, Optional, Union
import uuid

from src.core.entities.provider import redact_secrets
from src.core.ports.credential_vault import CredentialVaultPort

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class VaultProtectionError(RuntimeError):
    """Raised when OS credential protection or unprotection fails."""


class SecretProtector(ABC):
    """Strategy interface for protecting and unprotecting raw secret bytes."""

    @abstractmethod
    def protect(self, plaintext: bytes) -> bytes:
        """Encrypt raw secret bytes for persistent local storage."""

    @abstractmethod
    def unprotect(self, ciphertext: bytes) -> bytes:
        """Decrypt persisted bytes back into raw secret bytes."""


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


class WindowsDpapiProtector(SecretProtector):
    """Encrypts and decrypts secrets using Windows CryptProtectData / CryptUnprotectData."""

    def __init__(self, description: str = "AI Video Studio Credential") -> None:
        if sys.platform != "win32":
            raise VaultProtectionError("WindowsDpapiProtector requires Windows (win32).")

        self._description = description
        self._crypt32 = ctypes.windll.crypt32
        self._kernel32 = ctypes.windll.kernel32

        self._crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DATA_BLOB),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(_DATA_BLOB),
        ]
        self._crypt32.CryptProtectData.restype = wintypes.BOOL

        self._crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(_DATA_BLOB),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(_DATA_BLOB),
        ]
        self._crypt32.CryptUnprotectData.restype = wintypes.BOOL

        self._kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
        self._kernel32.LocalFree.restype = wintypes.HLOCAL

    def protect(self, plaintext: bytes) -> bytes:
        if not isinstance(plaintext, (bytes, bytearray)):
            raise TypeError("plaintext must be bytes.")

        raw = bytes(plaintext)
        buf = ctypes.create_string_buffer(raw, len(raw))
        blob_in = _DATA_BLOB(
            cbData=len(raw),
            pbData=ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _DATA_BLOB()

        ok = self._crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            self._description,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            err_code = ctypes.GetLastError()
            raise VaultProtectionError(f"CryptProtectData failed with Win32 error {err_code}.")

        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            if blob_out.pbData:
                self._kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not isinstance(ciphertext, (bytes, bytearray)):
            raise TypeError("ciphertext must be bytes.")

        raw = bytes(ciphertext)
        buf = ctypes.create_string_buffer(raw, len(raw))
        blob_in = _DATA_BLOB(
            cbData=len(raw),
            pbData=ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _DATA_BLOB()

        ok = self._crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            err_code = ctypes.GetLastError()
            raise VaultProtectionError(f"CryptUnprotectData failed with Win32 error {err_code}.")

        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            if blob_out.pbData:
                self._kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def get_default_vault_path() -> Path:
    """Return default local file path for encrypted DPAPI credential blobs."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        base_dir = Path(app_data) / "AI Video Studio"
    else:
        base_dir = Path.home() / ".ai_video_studio"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "secrets.vault.json"


class WindowsDpapiVault(CredentialVaultPort):
    """Persists DPAPI-protected secrets in a dedicated local vault file outside SQLite."""

    def __init__(
        self,
        vault_path: Optional[Union[str, Path]] = None,
        protector: Optional[SecretProtector] = None,
    ) -> None:
        self._vault_path = Path(vault_path) if vault_path is not None else get_default_vault_path()
        self._vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._protector = protector if protector is not None else WindowsDpapiProtector()
        self._lock = threading.RLock()

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    def store_secret(self, credential_ref: str, secret: str) -> None:
        ref = credential_ref.strip()
        if not ref:
            raise ValueError("credential_ref cannot be empty.")
        if not secret or not secret.strip():
            raise ValueError("secret cannot be empty.")

        cleaned_secret = secret.strip()
        try:
            encrypted = self._protector.protect(cleaned_secret.encode("utf-8"))
        except Exception as exc:
            safe_msg = redact_secrets(str(exc), [cleaned_secret]) or "Failed to protect credential."
            raise VaultProtectionError(safe_msg) from None

        encoded_blob = base64.b64encode(encrypted).decode("ascii")
        with self._lock:
            entries = self._load_entries()
            entries[ref] = encoded_blob
            self._save_entries(entries)

    def get_secret(self, credential_ref: str) -> Optional[str]:
        ref = credential_ref.strip()
        if not ref:
            return None

        with self._lock:
            entries = self._load_entries()
            encoded_blob = entries.get(ref)
            if not encoded_blob:
                return None

        try:
            encrypted = base64.b64decode(encoded_blob.encode("ascii"))
            plaintext_bytes = self._protector.unprotect(encrypted)
            return plaintext_bytes.decode("utf-8")
        except Exception as exc:
            raise VaultProtectionError(f"Failed to unprotect credential '{ref}': {exc}") from exc

    def delete_secret(self, credential_ref: str) -> bool:
        ref = credential_ref.strip()
        if not ref:
            return False

        with self._lock:
            entries = self._load_entries()
            if ref not in entries:
                return False
            del entries[ref]
            self._save_entries(entries)
            return True

    def has_secret(self, credential_ref: str) -> bool:
        ref = credential_ref.strip()
        if not ref:
            return False
        with self._lock:
            entries = self._load_entries()
            return ref in entries

    def _load_entries(self) -> Dict[str, str]:
        if not self._vault_path.exists():
            return {}
        raw = self._vault_path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        payload = json.loads(raw)
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return {}
        return {str(k): str(v) for k, v in entries.items()}

    def _save_entries(self, entries: Dict[str, str]) -> None:
        payload = {"version": 1, "entries": entries}
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        tmp_path = self._vault_path.with_name(f"{self._vault_path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(serialized, encoding="utf-8")
        os.replace(tmp_path, self._vault_path)
