"""Cloudflare Workers AI backend (remote inference over HTTPS).

Called instead of the local llama.cpp backend for templates listed in
`INFERENCE_REMOTE_TEMPLATES` (see inference/main.py). On any network or
API failure the caller falls through to the local backend, so this class
never has to know about degraded modes — it either returns a string or
raises.

The Cloudflare OpenAI-compatible endpoint accepts standard
`{model, messages, temperature, top_p, max_tokens}` and returns the
standard `choices[0].message.content` shape. `repetition_penalty` is
not part of the OpenAI vocabulary and is intentionally dropped — CF
would silently ignore it and it is a marginal knob for the paragraph-
length generations we do here.

Auth + endpoint:
  URL:    https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1/chat/completions
  Header: Authorization: Bearer {API_TOKEN}
"""
from __future__ import annotations

import os
from typing import Any

import httpx


_BASE_URL_FMT = ("https://api.cloudflare.com/client/v4/accounts/"
                 "{account_id}/ai/v1/chat/completions")


class CloudflareWorkersAIBackend:
    """Remote inference over the Cloudflare Workers AI OpenAI-compat API."""

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        timeout_s: float = 60.0,
    ):
        if not account_id or not api_token or not model:
            raise ValueError(
                "CloudflareWorkersAIBackend requires account_id, api_token, model")
        self._url = _BASE_URL_FMT.format(account_id=account_id)
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type":  "application/json",
        }
        self._timeout_s = timeout_s
        self.model_id = model

    def generate_from_messages(
        self,
        msgs: list[dict],
        max_tokens: int,
        temp: float,
        top_p: float,
        repetition_penalty: float | None = None,  # noqa: ARG002 — OpenAI has no equivalent
    ) -> str:
        body: dict[str, Any] = {
            "model":       self.model_id,
            "messages":    msgs,
            "temperature": temp,
            "top_p":       top_p,
            "max_tokens":  max_tokens,
        }
        # httpx.post is sync — matches the llama_backend interface. The
        # inference service already serialises generation under _lock in
        # main.py, so no concurrency benefit from going async here.
        r = httpx.post(self._url, headers=self._headers, json=body,
                       timeout=self._timeout_s)
        r.raise_for_status()
        data = r.json()
        return _extract_content(data)


def _extract_content(payload: Any) -> str:
    """Pull the generated text out of a Workers AI response.

    The OpenAI-compat endpoint we call returns:
        {"choices":[{"message":{"content":"..."}}], ...}
    but CF's non-OpenAI runners occasionally wrap responses in:
        {"result": {...}, "success": true, "errors": [], "messages": []}
    Handle both defensively so the backend is robust to a future CF
    change or a routing quirk that lands us on the native endpoint.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected response type: {type(payload).__name__}")

    # OpenAI-compat shape
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content:
            return content.strip()

    # CF native wrap: try again inside result
    result = payload.get("result")
    if isinstance(result, dict):
        # Sometimes an OpenAI-shaped body sits inside `result`.
        nested_choices = result.get("choices")
        if isinstance(nested_choices, list) and nested_choices:
            msg = (nested_choices[0] or {}).get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content:
                return content.strip()
        # CF native `run` returns `{"result": {"response": "..."}}`.
        response = result.get("response")
        if isinstance(response, str) and response:
            return response.strip()

    # Surface CF-side errors verbatim so ops can see what went wrong.
    errors = payload.get("errors") or (isinstance(result, dict) and result.get("errors"))
    if errors:
        raise ValueError(f"cloudflare api errors: {errors}")

    raise ValueError(
        f"unrecognised response shape; top-level keys: {sorted(payload.keys())}")


def backend_from_env() -> CloudflareWorkersAIBackend | None:
    """Instantiate the backend from environment, or return None if not
    configured. Called by inference/main.py at startup so an unset
    CF_ACCOUNT_ID silently disables the remote path (falls back to
    local-only)."""
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    api_token  = os.environ.get("CF_WORKERS_AI_TOKEN", "").strip()
    # `-awq` was deprecated 2026-05-30 despite still appearing in the docs
    # model catalog; `-fast` is CF's current optimised default for Llama
    # 3.1 8B and is the live cheapest option.
    model      = os.environ.get("CF_MODEL_ID",
                                "@cf/meta/llama-3.1-8b-instruct-fast").strip()
    if not account_id or not api_token:
        return None
    return CloudflareWorkersAIBackend(
        account_id=account_id, api_token=api_token, model=model)


if __name__ == "__main__":
    # Pure selfcheck — response parser only. No network I/O.
    # OpenAI-compat shape.
    assert _extract_content({
        "choices": [{"message": {"content": "hello world"}}],
    }) == "hello world"
    # CF-native wrap around OpenAI-shaped body.
    assert _extract_content({
        "result":  {"choices": [{"message": {"content": "wrapped"}}]},
        "success": True,
    }) == "wrapped"
    # CF-native `run` endpoint shape.
    assert _extract_content({
        "result":  {"response": "native run"},
        "success": True,
        "errors":  [],
    }) == "native run"
    # Trailing whitespace is stripped.
    assert _extract_content({
        "choices": [{"message": {"content": "  padded  \n"}}],
    }) == "padded"
    # Empty content is not a valid response — must raise so the caller
    # falls through to the local backend rather than serving "".
    try:
        _extract_content({"choices": [{"message": {"content": ""}}]})
    except ValueError:
        pass
    else:
        raise AssertionError("empty content must raise, not silently return ''")
    # CF-reported errors surface as ValueError so main.py can log + fall back.
    try:
        _extract_content({
            "success": False,
            "errors":  [{"code": 7003, "message": "no route for that URL"}],
        })
    except ValueError as e:
        assert "no route for that URL" in str(e)
    else:
        raise AssertionError("CF errors must surface as ValueError")
    # backend_from_env returns None when unconfigured.
    for key in ("CF_ACCOUNT_ID", "CF_WORKERS_AI_TOKEN"):
        os.environ.pop(key, None)
    assert backend_from_env() is None
    print("cloudflare_backend.py selfcheck OK")
