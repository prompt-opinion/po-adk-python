"""
Security middleware — API key authentication.

Every request is blocked unless it carries a valid X-API-Key header.
The only public endpoint is /.well-known/agent-card.json, which callers
need to discover the agent before they can authenticate.

In production, load keys from environment variables or a secrets manager
(e.g. Azure Key Vault, AWS Secrets Manager) rather than hardcoding them here.
"""
import json
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request  # kept for type hints in dispatch signature
from starlette.responses import JSONResponse

from shared.fhir_hook import extract_fhir_from_payload
from shared.logging_utils import redact_headers, safe_pretty_json, token_fingerprint

logger = logging.getLogger(__name__)

LOG_FULL_PAYLOAD = os.getenv("LOG_FULL_PAYLOAD", "true").lower() == "true"

def _load_valid_api_keys() -> set[str]:
    """
    Load allowed API keys from environment variables.

    Supported formats:
      API_KEYS=my-key-1,my-key-2
      API_KEY_PRIMARY=my-key-1
      API_KEY_SECONDARY=my-key-2

    This keeps the example multi-key friendly without shipping usable secrets
    in source control. In production, populate these values from a secret store.
    """
    keys = set()

    raw_keys = os.getenv("API_KEYS", "")
    if raw_keys:
        keys.update(k.strip() for k in raw_keys.split(",") if k.strip())

    for env_name in ("API_KEY_PRIMARY", "API_KEY_SECONDARY"):
        value = os.getenv(env_name, "").strip()
        if value:
            keys.add(value)

    return keys


VALID_API_KEYS: set[str] = _load_valid_api_keys()


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces X-API-Key authentication.

    It also logs every incoming request (with headers redacted) and, as a
    convenience, bridges FHIR metadata from params.message.metadata up to
    params.metadata so the ADK callback path can find it.
    """

    async def dispatch(self, request: Request, call_next):
        # Read and parse the body so we can log it and inspect metadata.
        body_bytes = await request.body()
        body_text  = body_bytes.decode("utf-8", errors="replace")
        parsed     = {}
        try:
            parsed = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            parsed = {}

        # Rewrite legacy PascalCase A2A method names to the current spec names.
        # Prompt Opinion (and other older clients) send e.g. "SendStreamingMessage"
        # but the installed a2a-sdk only registers "message/stream" / "message/send".
        _METHOD_ALIASES: dict[str, str] = {
            "SendMessage":          "message/send",
            "SendStreamingMessage": "message/send",   # PO client can't parse SSE; use non-streaming
            "GetTask":              "tasks/get",
            "CancelTask":           "tasks/cancel",
            "TaskResubscribe":      "tasks/resubscribe",
        }
        _ROLE_ALIASES: dict[str, str] = {
            "ROLE_USER":  "user",
            "ROLE_AGENT": "agent",
        }
        body_dirty = False

        if isinstance(parsed, dict) and parsed.get("method") in _METHOD_ALIASES:
            original_method = parsed["method"]
            parsed["method"] = _METHOD_ALIASES[original_method]
            body_dirty = True
            logger.info(
                "jsonrpc_method_rewritten original=%s rewritten=%s",
                original_method, parsed["method"],
            )

        # Normalise proto-style role values in every message in the payload.
        # Prompt Opinion sends ROLE_USER / ROLE_AGENT; the a2a-sdk expects user / agent.
        def _fix_roles(node):
            if isinstance(node, dict):
                if "role" in node and node["role"] in _ROLE_ALIASES:
                    node["role"] = _ROLE_ALIASES[node["role"]]
                for v in node.values():
                    _fix_roles(v)
            elif isinstance(node, list):
                for item in node:
                    _fix_roles(item)

        if isinstance(parsed, dict):
            before = json.dumps(parsed, sort_keys=True)
            _fix_roles(parsed)
            if json.dumps(parsed, sort_keys=True) != before:
                body_dirty = True
                logger.info("jsonrpc_roles_normalised")

        if body_dirty:
            body_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            request._body = body_bytes  # type: ignore[attr-defined]

        # Always log the JSON-RPC method so -32601 errors are immediately traceable.
        jsonrpc_method = parsed.get("method") if isinstance(parsed, dict) else None
        jsonrpc_id     = parsed.get("id")     if isinstance(parsed, dict) else None
        if jsonrpc_method:
            logger.info(
                "jsonrpc_request id=%s method=%s path=%s",
                jsonrpc_id, jsonrpc_method, request.url.path,
            )
        elif body_text:
            logger.warning(
                "jsonrpc_no_method_field path=%s body_preview=%s",
                request.url.path, body_text[:200],
            )

        if LOG_FULL_PAYLOAD:
            logger.info(
                "incoming_http_request path=%s method=%s headers=%s\npayload=\n%s",
                request.url.path, request.method,
                safe_pretty_json(redact_headers(dict(request.headers))),
                safe_pretty_json(parsed) if parsed else body_text,
            )

        # Bridge FHIR metadata from message.metadata → params.metadata so that
        # the ADK before_model_callback (fhir_hook.extract_fhir_context) can
        # find it regardless of where the caller placed it.
        fhir_key, fhir_data = extract_fhir_from_payload(parsed)
        if isinstance(parsed, dict):
            params = parsed.get("params")
            if isinstance(params, dict):
                if fhir_key and fhir_data and not params.get("metadata"):
                    params["metadata"] = {fhir_key: fhir_data}
                    body_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
                    # Mutate Starlette's cached body directly.
                    # BaseHTTPMiddleware captures `wrapped_receive` from the original
                    # _CachedRequest object; call_next() reads from that, not from any
                    # cloned Request we might create.  Setting request._body is the only
                    # way to make the modified bytes visible to the downstream handler.
                    request._body = body_bytes  # type: ignore[attr-defined]
                    logger.info(
                        "FHIR_METADATA_BRIDGED source=message.metadata target=params.metadata key=%s",
                        fhir_key,
                    )
                if fhir_data:
                    logger.info("FHIR_URL_FOUND value=%s",         fhir_data.get("fhirUrl", "[EMPTY]"))
                    logger.info("FHIR_TOKEN_FOUND fingerprint=%s", token_fingerprint(fhir_data.get("fhirToken", "")))
                    logger.info("FHIR_PATIENT_FOUND value=%s",     fhir_data.get("patientId", "[EMPTY]"))
                else:
                    logger.info("FHIR_NOT_FOUND_IN_PAYLOAD keys_checked=params.metadata,message.metadata")

        # Agent-card endpoint is intentionally public — it tells callers that
        # an API key IS required before they start authenticating.
        if request.url.path == "/.well-known/agent-card.json":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(
                "security_rejected_missing_api_key path=%s method=%s",
                request.url.path, request.method,
            )
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "detail": "X-API-Key header is required"},
            )

        if api_key not in VALID_API_KEYS:
            logger.warning(
                "security_rejected_invalid_api_key path=%s method=%s key_prefix=%s",
                request.url.path, request.method, api_key[:6],
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden", "detail": "Invalid API key"},
            )

        logger.info(
            "security_authorized path=%s method=%s key_prefix=%s",
            request.url.path, request.method, api_key[:6],
        )
        response = await call_next(request)

        # Only post-process JSON responses (not SSE streams).
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            resp_body = b""
            async for chunk in response.body_iterator:
                resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
            try:
                resp_parsed = json.loads(resp_body)

                # Re-shape the JSON-RPC response into the PO a2a+json envelope:
                #   {"task": { id, contextId, status, artifacts }}
                # Differences from what a2a-sdk returns:
                #   - No jsonrpc/id wrapper — just {"task": {...}}
                #   - status.state uses proto enum   e.g. "TASK_STATE_COMPLETED"
                #   - artifact parts have no "kind" field — just {"text": "..."}
                #   - Content-Type: application/a2a+json
                _STATE_MAP = {
                    "completed":      "TASK_STATE_COMPLETED",
                    "working":        "TASK_STATE_WORKING",
                    "submitted":      "TASK_STATE_SUBMITTED",
                    "input-required": "TASK_STATE_INPUT_REQUIRED",
                    "failed":         "TASK_STATE_FAILED",
                    "canceled":       "TASK_STATE_CANCELED",
                }
                result = resp_parsed.get("result") if isinstance(resp_parsed, dict) else None
                if isinstance(result, dict) and result.get("kind") == "task":
                    # Build clean task object
                    task: dict = {
                        "id":        result.get("id"),
                        "contextId": result.get("contextId"),
                    }

                    # Status — map state to proto enum
                    status = result.get("status", {})
                    raw_state = status.get("state", "")
                    task["status"] = {"state": _STATE_MAP.get(raw_state, raw_state.upper())}

                    # Artifacts — strip "kind" from each part
                    clean_artifacts = []
                    for artifact in result.get("artifacts", []):
                        clean_parts = []
                        for part in artifact.get("parts", []):
                            clean_part = {k: v for k, v in part.items() if k != "kind"}
                            clean_parts.append(clean_part)
                        clean_artifact = {k: v for k, v in artifact.items() if k != "parts"}
                        clean_artifact["parts"] = clean_parts
                        clean_artifacts.append(clean_artifact)
                    task["artifacts"] = clean_artifacts

                    # Keep JSON-RPC envelope; nest task under "task" key in result
                    resp_parsed["result"] = {"task": task}
                    logger.info("response_reshaped_to_po_a2a_json task_id=%s state=%s",
                                task.get("id"), task["status"]["state"])

                resp_body = json.dumps(resp_parsed, ensure_ascii=False).encode("utf-8")

                if LOG_FULL_PAYLOAD:
                    logger.info(
                        "outgoing_response status=%s content_type=%s\nbody=\n%s",
                        response.status_code, content_type,
                        safe_pretty_json(resp_parsed),
                    )
            except Exception:
                logger.warning(
                    "outgoing_response_parse_failed status=%s body_raw=%s",
                    response.status_code, resp_body[:500],
                )

            from starlette.responses import Response as StarletteResponse
            headers = dict(response.headers)
            headers["content-length"] = str(len(resp_body))
            # PO expects application/a2a+json, not application/json
            return StarletteResponse(
                content=resp_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        return response
