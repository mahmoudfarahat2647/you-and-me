"""HTTP provider gateway adapter supporting Gemini, OpenAI-compatible, and local Ollama."""
from typing import Any, Callable, Dict, List, Optional, Tuple
import httpx

from src.core.dto.provider_dto import (
    GatewayConnectionProbeResult,
    ProviderOperationRequest,
    ProviderOperationResponse,
)
from src.core.entities.budget import ExternalJobStatus
from src.core.entities.provider import (
    ProviderCapability,
    ProviderType,
    redact_secrets,
)
from src.core.ports.provider_gateway import ProviderGateway


def _unique_ordered_capabilities(caps: List[ProviderCapability]) -> Tuple[ProviderCapability, ...]:
    order = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.RESEARCH,
        ProviderCapability.TTS,
        ProviderCapability.VIDEO_GENERATION,
    ]
    present = set(caps)
    return tuple(c for c in order if c in present)


def _infer_openai_capabilities(model_ids: List[str]) -> Tuple[ProviderCapability, ...]:
    caps: List[ProviderCapability] = []
    for model_id in model_ids:
        lower = model_id.lower()
        if "tts" in lower or "audio" in lower or "speech" in lower:
            caps.append(ProviderCapability.TTS)
        if any(token in lower for token in ("sora", "veo", "video", "runway", "kling")):
            caps.append(ProviderCapability.VIDEO_GENERATION)
        if any(
            token in lower
            for token in ("gpt", "o1", "o3", "o4", "claude", "llama", "qwen", "mistral", "deepseek", "gemini")
        ):
            caps.extend([ProviderCapability.TEXT_GENERATION, ProviderCapability.RESEARCH])
    if model_ids and not caps:
        caps.append(ProviderCapability.TEXT_GENERATION)
    return _unique_ordered_capabilities(caps)


def _infer_gemini_capabilities(models_payload: List[Dict[str, Any]]) -> Tuple[Tuple[str, ...], Tuple[ProviderCapability, ...]]:
    model_names: List[str] = []
    caps: List[ProviderCapability] = []
    for item in models_payload:
        raw_name = str(item.get("name", "")).strip()
        if not raw_name:
            continue
        clean_name = raw_name.removeprefix("models/")
        model_names.append(clean_name)
        methods = {str(m) for m in item.get("supportedGenerationMethods", [])}
        lower = clean_name.lower()
        if "generateContent" in methods or "gemini" in lower:
            caps.extend([ProviderCapability.TEXT_GENERATION, ProviderCapability.RESEARCH])
        if "predictLongRunning" in methods or "veo" in lower:
            caps.append(ProviderCapability.VIDEO_GENERATION)
        if "tts" in lower:
            caps.append(ProviderCapability.TTS)
    return tuple(model_names), _unique_ordered_capabilities(caps)


def _extract_reported_cost(data: Dict[str, Any], headers: httpx.Headers) -> Optional[float]:
    for header_name in ("x-cost-usd", "x-reported-cost-usd"):
        raw = headers.get(header_name)
        if raw is not None:
            try:
                return float(raw)
            except ValueError:
                pass
    for key in ("cost_usd", "reported_cost_usd"):
        val = data.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


class HttpProviderGateway(ProviderGateway):
    """Real HTTP provider gateway using httpx with injectable transport for deterministic tests."""

    def __init__(
        self,
        transport: Optional[httpx.BaseTransport] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            timeout=self._timeout_seconds,
        )

    def test_connection(
        self,
        provider_type: ProviderType,
        base_url: str,
        api_key: Optional[str],
    ) -> GatewayConnectionProbeResult:
        clean_base = base_url.strip().rstrip("/")
        handlers: Dict[ProviderType, Callable[[str, Optional[str]], GatewayConnectionProbeResult]] = {
            ProviderType.GEMINI: self._probe_gemini,
            ProviderType.OPENAI_COMPATIBLE: self._probe_openai,
            ProviderType.LOCAL_OLLAMA: self._probe_ollama,
        }
        handler = handlers[provider_type]
        return handler(clean_base, api_key)

    def submit_operation(
        self,
        request: ProviderOperationRequest,
    ) -> ProviderOperationResponse:
        handlers: Dict[ProviderType, Callable[[ProviderOperationRequest], ProviderOperationResponse]] = {
            ProviderType.GEMINI: self._submit_gemini,
            ProviderType.OPENAI_COMPATIBLE: self._submit_openai,
            ProviderType.LOCAL_OLLAMA: self._submit_ollama,
        }
        return handlers[request.provider_type](request)

    def poll_operation(
        self,
        provider_type: ProviderType,
        base_url: str,
        api_key: Optional[str],
        external_job_id: str,
    ) -> ProviderOperationResponse:
        clean_base = base_url.strip().rstrip("/")
        if provider_type == ProviderType.GEMINI:
            return self._poll_gemini(clean_base, api_key, external_job_id)
        if provider_type == ProviderType.OPENAI_COMPATIBLE:
            return self._poll_openai(clean_base, api_key, external_job_id)
        return ProviderOperationResponse(
            accepted=False,
            external_job_id=external_job_id,
            status=ExternalJobStatus.UNCERTAIN,
            error_message="Polling is not supported for local Ollama synchronous endpoints.",
        )

    def _probe_gemini(self, base_url: str, api_key: Optional[str]) -> GatewayConnectionProbeResult:
        endpoint = f"{base_url}/v1beta/models"
        headers = {"x-goog-api-key": api_key} if api_key else {}
        try:
            with self._make_client() as client:
                resp = client.get(endpoint, headers=headers)
            if resp.status_code != 200:
                return GatewayConnectionProbeResult(
                    success=False,
                    supported_capabilities=(),
                    verified_models=(),
                    message=self._format_http_error("Gemini", resp, api_key),
                    endpoint_checked=endpoint,
                )
            data = resp.json()
            models_payload = data.get("models", [])
            models, caps = _infer_gemini_capabilities(models_payload if isinstance(models_payload, list) else [])
            return GatewayConnectionProbeResult(
                success=True,
                supported_capabilities=caps,
                verified_models=models,
                message=f"Connected to Gemini API ({len(models)} model(s) discovered).",
                endpoint_checked=endpoint,
            )
        except Exception as exc:
            return GatewayConnectionProbeResult(
                success=False,
                supported_capabilities=(),
                verified_models=(),
                message=redact_secrets(str(exc), [api_key]) or "Gemini connection failed.",
                endpoint_checked=endpoint,
            )

    def _probe_openai(self, base_url: str, api_key: Optional[str]) -> GatewayConnectionProbeResult:
        endpoint = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with self._make_client() as client:
                resp = client.get(endpoint, headers=headers)
            if resp.status_code != 200:
                return GatewayConnectionProbeResult(
                    success=False,
                    supported_capabilities=(),
                    verified_models=(),
                    message=self._format_http_error("OpenAI-compatible", resp, api_key),
                    endpoint_checked=endpoint,
                )
            data = resp.json()
            raw_models = data.get("data", [])
            model_ids = [
                str(m.get("id")).strip()
                for m in (raw_models if isinstance(raw_models, list) else [])
                if isinstance(m, dict) and m.get("id")
            ]
            caps = _infer_openai_capabilities(model_ids)
            return GatewayConnectionProbeResult(
                success=True,
                supported_capabilities=caps,
                verified_models=tuple(model_ids),
                message=f"Connected to OpenAI-compatible API ({len(model_ids)} model(s) discovered).",
                endpoint_checked=endpoint,
            )
        except Exception as exc:
            return GatewayConnectionProbeResult(
                success=False,
                supported_capabilities=(),
                verified_models=(),
                message=redact_secrets(str(exc), [api_key]) or "OpenAI-compatible connection failed.",
                endpoint_checked=endpoint,
            )

    def _probe_ollama(self, base_url: str, api_key: Optional[str]) -> GatewayConnectionProbeResult:
        endpoint = f"{base_url}/api/tags"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with self._make_client() as client:
                resp = client.get(endpoint, headers=headers)
            if resp.status_code != 200:
                return GatewayConnectionProbeResult(
                    success=False,
                    supported_capabilities=(),
                    verified_models=(),
                    message=self._format_http_error("Local Ollama", resp, api_key),
                    endpoint_checked=endpoint,
                )
            data = resp.json()
            raw_models = data.get("models", [])
            model_names = [
                str(m.get("name")).strip()
                for m in (raw_models if isinstance(raw_models, list) else [])
                if isinstance(m, dict) and m.get("name")
            ]
            caps = (
                (ProviderCapability.TEXT_GENERATION, ProviderCapability.RESEARCH)
                if model_names
                else ()
            )
            return GatewayConnectionProbeResult(
                success=True,
                supported_capabilities=caps,
                verified_models=tuple(model_names),
                message=f"Connected to Local Ollama ({len(model_names)} model(s) available).",
                endpoint_checked=endpoint,
            )
        except Exception as exc:
            return GatewayConnectionProbeResult(
                success=False,
                supported_capabilities=(),
                verified_models=(),
                message=redact_secrets(str(exc), [api_key]) or "Local Ollama connection failed.",
                endpoint_checked=endpoint,
            )

    def _submit_gemini(self, request: ProviderOperationRequest) -> ProviderOperationResponse:
        clean_base = request.base_url.strip().rstrip("/")
        action = (
            "predictLongRunning"
            if request.capability == ProviderCapability.VIDEO_GENERATION
            else "generateContent"
        )
        endpoint = f"{clean_base}/v1beta/models/{request.model}:{action}"
        headers = {
            "X-Request-Key": request.request_key,
            "Content-Type": "application/json",
        }
        if request.api_key:
            headers["x-goog-api-key"] = request.api_key

        try:
            with self._make_client() as client:
                resp = client.post(endpoint, headers=headers, json=request.payload)
            return self._parse_submission_response(
                resp=resp,
                api_key=request.api_key,
                async_by_default=(action == "predictLongRunning"),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=None,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=redact_secrets(str(exc), [request.api_key]),
            )

    def _submit_openai(self, request: ProviderOperationRequest) -> ProviderOperationResponse:
        clean_base = request.base_url.strip().rstrip("/")
        path_map = {
            ProviderCapability.TEXT_GENERATION: "/chat/completions",
            ProviderCapability.RESEARCH: "/chat/completions",
            ProviderCapability.TTS: "/audio/speech",
            ProviderCapability.VIDEO_GENERATION: "/videos/generations",
        }
        endpoint = f"{clean_base}{path_map[request.capability]}"
        headers = {
            "Idempotency-Key": request.request_key,
            "Content-Type": "application/json",
        }
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        body = dict(request.payload)
        body.setdefault("model", request.model)

        try:
            with self._make_client() as client:
                resp = client.post(endpoint, headers=headers, json=body)
            return self._parse_submission_response(
                resp=resp,
                api_key=request.api_key,
                async_by_default=(request.capability == ProviderCapability.VIDEO_GENERATION),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=None,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=redact_secrets(str(exc), [request.api_key]),
            )

    def _submit_ollama(self, request: ProviderOperationRequest) -> ProviderOperationResponse:
        clean_base = request.base_url.strip().rstrip("/")
        endpoint = f"{clean_base}/api/chat"
        headers = {"X-Request-Key": request.request_key, "Content-Type": "application/json"}
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        body = dict(request.payload)
        body.setdefault("model", request.model)
        body.setdefault("stream", False)

        try:
            with self._make_client() as client:
                resp = client.post(endpoint, headers=headers, json=body)
            return self._parse_submission_response(
                resp=resp,
                api_key=request.api_key,
                async_by_default=False,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=None,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=redact_secrets(str(exc), [request.api_key]),
            )

    def _poll_gemini(
        self,
        base_url: str,
        api_key: Optional[str],
        external_job_id: str,
    ) -> ProviderOperationResponse:
        op_path = external_job_id.lstrip("/")
        endpoint = f"{base_url}/v1beta/{op_path}"
        headers = {"x-goog-api-key": api_key} if api_key else {}
        try:
            with self._make_client() as client:
                resp = client.get(endpoint, headers=headers)
            if resp.status_code >= 500:
                return ProviderOperationResponse(
                    accepted=False,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.UNCERTAIN,
                    error_message=self._format_http_error("Gemini", resp, api_key),
                )
            if resp.status_code >= 400:
                return ProviderOperationResponse(
                    accepted=False,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.FAILED,
                    reported_cost_usd=0.0,
                    error_message=self._format_http_error("Gemini", resp, api_key),
                )
            data = resp.json()
            if data.get("done") is True:
                if data.get("error"):
                    err_msg = redact_secrets(str(data.get("error")), [api_key])
                    return ProviderOperationResponse(
                        accepted=False,
                        external_job_id=external_job_id,
                        status=ExternalJobStatus.FAILED,
                        reported_cost_usd=_extract_reported_cost(data, resp.headers),
                        error_message=err_msg,
                    )
                return ProviderOperationResponse(
                    accepted=True,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.SUCCEEDED,
                    output_summary="Operation completed.",
                    reported_cost_usd=_extract_reported_cost(data, resp.headers),
                )
            return ProviderOperationResponse(
                accepted=True,
                external_job_id=external_job_id,
                status=ExternalJobStatus.SUBMITTED,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=external_job_id,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=redact_secrets(str(exc), [api_key]),
            )

    def _poll_openai(
        self,
        base_url: str,
        api_key: Optional[str],
        external_job_id: str,
    ) -> ProviderOperationResponse:
        endpoint = f"{base_url}/videos/{external_job_id}"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with self._make_client() as client:
                resp = client.get(endpoint, headers=headers)
            if resp.status_code >= 500:
                return ProviderOperationResponse(
                    accepted=False,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.UNCERTAIN,
                    error_message=self._format_http_error("OpenAI-compatible", resp, api_key),
                )
            if resp.status_code >= 400:
                return ProviderOperationResponse(
                    accepted=False,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.FAILED,
                    reported_cost_usd=0.0,
                    error_message=self._format_http_error("OpenAI-compatible", resp, api_key),
                )
            data = resp.json()
            raw_status = str(data.get("status", "")).lower()
            if raw_status in ("completed", "succeeded", "done"):
                return ProviderOperationResponse(
                    accepted=True,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.SUCCEEDED,
                    output_summary="Video job completed.",
                    reported_cost_usd=_extract_reported_cost(data, resp.headers),
                )
            if raw_status in ("failed", "cancelled", "error"):
                return ProviderOperationResponse(
                    accepted=False,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.FAILED,
                    reported_cost_usd=_extract_reported_cost(data, resp.headers),
                    error_message=redact_secrets(str(data.get("error", "External job failed.")), [api_key]),
                )
            return ProviderOperationResponse(
                accepted=True,
                external_job_id=external_job_id,
                status=ExternalJobStatus.SUBMITTED,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=external_job_id,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=redact_secrets(str(exc), [api_key]),
            )

    def _parse_submission_response(
        self,
        *,
        resp: httpx.Response,
        api_key: Optional[str],
        async_by_default: bool,
    ) -> ProviderOperationResponse:
        header_job_id = resp.headers.get("x-request-id") or resp.headers.get("request-id")
        if resp.status_code >= 500:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=header_job_id,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=self._format_http_error("Provider", resp, api_key),
            )
        if resp.status_code >= 400:
            return ProviderOperationResponse(
                accepted=False,
                external_job_id=header_job_id,
                status=ExternalJobStatus.FAILED,
                reported_cost_usd=0.0,
                error_message=self._format_http_error("Provider", resp, api_key),
            )

        content_type = resp.headers.get("content-type", "")
        data: Dict[str, Any] = {}
        if "application/json" in content_type or resp.text.strip().startswith("{"):
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    data = parsed
            except ValueError:
                data = {}

        external_job_id = (
            data.get("name")
            or data.get("id")
            or data.get("responseId")
            or header_job_id
        )
        if external_job_id is not None:
            external_job_id = str(external_job_id)

        reported_cost = _extract_reported_cost(data, resp.headers)
        if async_by_default and data.get("done") is not True:
            raw_status = str(data.get("status", "")).lower()
            if raw_status not in ("completed", "succeeded"):
                return ProviderOperationResponse(
                    accepted=True,
                    external_job_id=external_job_id,
                    status=ExternalJobStatus.SUBMITTED,
                    reported_cost_usd=reported_cost,
                )

        return ProviderOperationResponse(
            accepted=True,
            external_job_id=external_job_id,
            status=ExternalJobStatus.SUCCEEDED,
            output_summary="Provider request succeeded.",
            reported_cost_usd=reported_cost,
        )

    @staticmethod
    def _format_http_error(label: str, resp: httpx.Response, api_key: Optional[str]) -> str:
        snippet = resp.text[:300] if resp.text else ""
        raw_msg = f"{label} HTTP {resp.status_code}: {snippet}".strip()
        return redact_secrets(raw_msg, [api_key]) or f"{label} HTTP {resp.status_code}"
