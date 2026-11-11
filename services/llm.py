"""Async client for the configured OpenAI-compatible chat endpoint.

Defaults to LM Studio's local server; configuration can select another
compatible endpoint. Returns None and records failure details when a request
fails.
"""

import logging
import asyncio

import aiohttp

import config

_last_error = None
_last_failure = None
_chat_lock = asyncio.Lock()
_resolved_model = None


def last_error() -> str | None:
    return _last_error


def failure_kind() -> str | None:
    """Stable failure category for callers; transport details stay in logs."""
    return _last_failure


def _failure_from_http(status: int, body: str) -> str:
    text = (body or "").lower()
    if any(sign in text for sign in (
        "model not found", "no models loaded", "not loaded", "was unloaded",
        "has not started loading", "failed to load model",
    )):
        return "model_missing"
    if status == 408 or status == 429 or status >= 500:
        return "busy"
    return "rejected"


def failure_message(command: str = "") -> str:
    """Concise chat-facing failure text with no exception repr or HTTP body."""
    subject = f"~{command} failed" if command else "Local AI request failed"
    if _last_failure == "offline":
        return f"{subject}: LM Studio's server is not running."
    if _last_failure == "model_missing":
        return f"{subject}: the configured chat model is not loaded in LM Studio."
    if _last_failure == "timeout":
        return f"{subject}: local AI timed out. It may still be loading; retry shortly."
    if _last_failure == "busy":
        return f"{subject}: local AI is busy or loading. Retry shortly."
    if _last_failure == "rejected":
        return f"{subject}: local AI rejected the request. Check the loaded model."
    if _last_failure == "invalid_response":
        return f"{subject}: local AI returned an invalid response."
    return f"{subject}: local AI returned no usable response."


async def _pick_model(session) -> str:
    """The model id to send. Newer LM Studio rejects the legacy 'local' id, so
    if config.LLM_MODEL is blank/'local' we auto-detect the first non-embedding
    loaded model. A real configured id is used as-is (also how the A/B picks
    each model)."""
    global _resolved_model
    cfg = (config.LLM_MODEL or "").strip()
    if cfg and cfg.lower() != "local":
        return cfg
    if _resolved_model:
        return _resolved_model
    try:
        base = config.LLM_ENDPOINT.split("/v1/")[0]
        async with session.get(base + "/v1/models") as r:
            ids = [m["id"] for m in (await r.json()).get("data", [])]
        for mid in ids:
            if "embed" not in mid.lower():
                _resolved_model = mid
                return mid
    except Exception:
        pass
    return "local"


async def chat(messages, max_tokens: int = 120, temperature: float = 0.85,
               stop=None, model: str = None) -> str | None:
    """model: explicit model id (e.g. the live A/B roll); default = config."""
    global _last_error, _last_failure
    _last_error = None
    _last_failure = None
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if stop:
        payload["stop"] = stop
    try:
        async with _chat_lock:
            timeout = aiohttp.ClientTimeout(total=config.LLM_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload["model"] = model or await _pick_model(session)
                async with session.post(config.LLM_ENDPOINT, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        _last_error = f"HTTP {resp.status}: {body[:200]}"
                        _last_failure = _failure_from_http(resp.status, body)
                        logging.warning(f"LLM endpoint {_last_error}")
                        return None
                    try:
                        data = await resp.json()
                        text = (data["choices"][0]["message"]["content"] or "").strip()
                    except (KeyError, IndexError, TypeError, ValueError) as exc:
                        _last_error = f"invalid response: {type(exc).__name__}"
                        _last_failure = "invalid_response"
                        logging.warning("LLM endpoint returned an invalid response: %r", exc)
                        return None
                    if not text:
                        _last_error = "empty response"
                        _last_failure = "empty"
                        return None
                    return text
    except asyncio.TimeoutError:
        _last_error = f"timeout after {config.LLM_TIMEOUT}s"
        _last_failure = "timeout"
        logging.warning(f"LLM call failed ({config.LLM_ENDPOINT}): {_last_error}")
        return None
    except aiohttp.ClientConnectorError as e:
        _last_error = f"{type(e).__name__}: {e!r}"
        _last_failure = "offline"
        logging.warning(f"LLM call failed ({config.LLM_ENDPOINT}): {_last_error}")
        return None
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e!r}"
        text = str(e).lower()
        _last_failure = "offline" if any(sign in text for sign in (
            "10061", "1225", "connection refused", "actively refused",
            "refused the network connection", "clientconnectorerror",
        )) else "invalid_response"
        logging.warning(f"LLM call failed ({config.LLM_ENDPOINT}): {_last_error}")
        return None


async def available() -> bool:
    """Quick reachability check for local/remote OpenAI-compatible endpoints."""
    base = config.LLM_ENDPOINT.split("/v1/")[0]
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(base + "/v1/models") as resp:
                return resp.status == 200
    except Exception:
        return False
