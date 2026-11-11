"""Process-wide queue for model requests.

Commands, resident personas and ambient reactions share one request lane.
"""

import asyncio
import logging
import time
from collections import deque

import aiohttp

import config

_enabled = bool(getattr(config, "LLM_ENABLED", True))
_probe_cache = {}
_PROBE_CACHE_SECONDS = 1.0

_lock = asyncio.Lock()
_queue = deque()
_entries = {}
_user_active = {}
_sig_active = {}
_cancelled = set()
_running = None
_ticket = 0


def _base_url() -> str:
    return config.LLM_ENDPOINT.split("/v1/")[0]


def enabled() -> bool:
    return _enabled


def set_enabled(value: bool) -> None:
    """Enable/disable live model work for this bot process."""
    global _enabled
    _enabled = bool(value)
    _probe_cache.clear()


def _model_ids_state(ids, capability: str) -> str:
    """Validate that the configured capability is represented in /v1/models."""
    ids = {str(model_id).strip().lower() for model_id in ids if model_id}
    if not ids:
        return "model_missing"

    chat_model = str(getattr(config, "LLM_MODEL", "") or "").strip().lower()
    embed_model = str(getattr(config, "LLM_EMBED_MODEL", "") or "").strip().lower()

    needs_chat = capability in {"chat", "both"}
    needs_embedding = capability in {"embedding", "both"}
    if needs_embedding:
        if not embed_model:
            return "unconfigured"
        if embed_model not in ids:
            return "model_missing"
    if needs_chat:
        if chat_model and chat_model != "local":
            if chat_model not in ids:
                return "model_missing"
        else:
            # "local" means auto-pick the first non-embedding model.
            chat_ids = {model_id for model_id in ids
                        if model_id != embed_model and "embed" not in model_id}
            if not chat_ids:
                return "model_missing"
    return "up"


async def server_state(capability: str = "any", *, force: bool = False) -> str:
    """Return disabled, up, busy, offline, model_missing, or unconfigured.

    "offline" is reserved for connection-refused / host-unreachable style
    failures. Timeouts and odd HTTP states usually mean LM Studio is busy,
    loading, or wedged, not literally off.
    """
    if not enabled():
        return "disabled"
    capability = capability if capability in {"any", "chat", "embedding", "both"} else "any"
    now = time.monotonic()
    cached = _probe_cache.get(capability)
    if cached and not force and now - cached[0] <= _PROBE_CACHE_SECONDS:
        return cached[1]

    state = "busy"
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(_base_url() + "/v1/models") as resp:
                if resp.status != 200:
                    state = "busy"
                elif capability == "any":
                    state = "up"
                else:
                    try:
                        payload = await resp.json()
                        ids = [row.get("id") for row in payload.get("data", [])
                               if isinstance(row, dict)]
                        state = _model_ids_state(ids, capability)
                    except Exception as exc:
                        logging.debug("model list response was invalid: %r", exc)
                        state = "busy"
    except asyncio.TimeoutError:
        state = "busy"
    except aiohttp.ClientConnectorError:
        state = "offline"
    except OSError as exc:
        text = str(exc).lower()
        if any(sign in text for sign in (
            "10061", "1225", "connection refused", "actively refused",
            "refused the network connection",
        )):
            state = "offline"
        else:
            state = "busy"
    except Exception as exc:
        logging.debug("model server probe was inconclusive: %r", exc)
        state = "busy"
    _probe_cache[capability] = (time.monotonic(), state)
    return state


def availability_message(state: str, command: str = "", capability: str = "chat") -> str:
    """Stable chat-facing status; never includes transport exception details."""
    subject = f"~{command} unavailable" if command else "Local AI unavailable"
    if state == "disabled":
        return f"{subject}: local AI commands are disabled."
    if state == "offline":
        return f"{subject}: LM Studio's server is not running."
    if state == "unconfigured":
        if capability == "embedding":
            kind = "embedding"
        elif capability == "both":
            kind = "chat or embedding"
        else:
            kind = "chat"
        return f"{subject}: the {kind} model is not configured."
    if state == "model_missing":
        if capability == "embedding":
            kind = "embedding model"
        elif capability == "both":
            kind = "chat or embedding model"
        else:
            kind = "chat model"
        return f"{subject}: the required {kind} is not loaded in LM Studio."
    if state == "rejected":
        return f"{subject}: local AI rejected the request. Check the loaded model."
    return f"{subject}: local AI is busy or loading. Retry shortly."


def is_busy() -> bool:
    return _lock.locked() or bool(_queue)


def status() -> str:
    running = _entries.get(_running)
    pending = [_entries[t] for t in list(_queue) if t in _entries]
    if not running and not pending:
        return "local AI: disabled | queue idle" if not enabled() else "local AI queue: idle"
    bits = []
    if running:
        bits.append(f"running {running['label']}")
    if pending:
        listed = " ".join(f"#{i + 1}:{entry['label']}" for i, entry in enumerate(pending[:5]))
        bits.append("queued " + listed)
        if len(pending) > 5:
            bits.append(f"+{len(pending) - 5} more")
    prefix = "local AI: disabled | queue: " if not enabled() else "local AI queue: "
    return prefix + " | ".join(bits)


def clear_pending() -> int:
    pending = list(_queue)
    _cancelled.update(pending)
    for ticket in pending:
        entry = _entries.pop(ticket, None)
        if entry:
            if entry.get("user_key") and _user_active.get(entry["user_key"]) == ticket:
                _user_active.pop(entry["user_key"], None)
            if entry.get("sig") and _sig_active.get(entry["sig"]) == ticket:
                _sig_active.pop(entry["sig"], None)
    _queue.clear()
    return len(pending)


def running_ticket():
    return _running


def _short_label(label: str) -> str:
    label = " ".join((label or "model").split())
    return label[:48]


async def _notify(send, text: str):
    if send:
        await send(text)


async def submit(
    *,
    label: str,
    work,
    model_kind: str = "required",
    capability: str = "chat",
    command: str = "",
    send=None,
    user: str = "",
    user_key: str | None = None,
    sig: str | None = None,
    queue_if_busy: bool = True,
    announce: bool = True,
):
    """Run one model job through the shared queue.

    model_kind is "required" for work that cannot answer without local AI and
    "optional" for optional model-written output. Optional work is skipped when the
    model is disabled/unavailable/busy; its caller supplies the local fallback.
    work must be an async callable.
    """
    global _ticket, _running

    user_key = (user_key or "").lower() or None
    sig = (sig or "").strip().lower() or None
    initial_state = None

    if not enabled():
        if model_kind == "required":
            await _notify(send, availability_message("disabled", command, capability))
        return None

    if model_kind == "optional" and is_busy():
        return None

    if not is_busy():
        state = await server_state(capability)
        initial_state = state
        if state in {"disabled", "offline", "model_missing", "unconfigured"}:
            if model_kind == "required":
                await _notify(send, availability_message(state, command, capability))
            return None
        if model_kind == "optional" and state != "up":
            return None

    if not queue_if_busy and is_busy():
        return None

    if user_key and user_key in _user_active:
        await _notify(send, f"@{user} wait for your current model command to finish.")
        return None
    if sig and sig in _sig_active:
        await _notify(send, f"@{user} that model command is already queued/running.")
        return None

    _ticket += 1
    ticket = _ticket
    queued = _lock.locked() or bool(_queue)
    entry = {
        "ticket": ticket,
        "label": _short_label(label),
        "user": user,
        "user_key": user_key,
        "sig": sig,
        "queued": queued,
    }
    _entries[ticket] = entry
    if user_key:
        _user_active[user_key] = ticket
    if sig:
        _sig_active[sig] = ticket

    if queued:
        _queue.append(ticket)
        if announce:
            await _notify(send, f"@{user} local AI queue: position {len(_queue)}.")
    elif announce:
        await _notify(send, f"@{user} local AI: processing.")

    try:
        async with _lock:
            if ticket in _cancelled:
                return None
            try:
                _queue.remove(ticket)
            except ValueError:
                pass
            _running = ticket
            if entry.get("queued") and announce:
                await _notify(send, f"@{user} local AI: processing.")
            # An immediately-started job was just probed above. Re-probe only
            # after an actual queue wait, where server/model state may have
            # changed while another command ran.
            state = (
                await server_state(capability, force=True)
                if entry.get("queued") else initial_state or await server_state(capability)
            )
            if state in {"disabled", "offline", "model_missing", "unconfigured"}:
                if model_kind == "required":
                    await _notify(send, availability_message(state, command, capability))
                return None
            if model_kind == "optional" and state != "up":
                return None
            return await work()
    finally:
        if _running == ticket:
            _running = None
        _cancelled.discard(ticket)
        _entries.pop(ticket, None)
        if user_key and _user_active.get(user_key) == ticket:
            _user_active.pop(user_key, None)
        if sig and _sig_active.get(sig) == ticket:
            _sig_active.pop(sig, None)
        try:
            _queue.remove(ticket)
        except ValueError:
            pass
