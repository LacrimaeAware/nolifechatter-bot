"""Translation providers.

DeepL (free tier, header-based auth) over aiohttp so a slow or stalled
provider delays one translation instead of the whole bot. Kept separate so a
second provider (Google is wired in services/message_service.py) can be added
or rotated to spread free-tier usage.
"""

import asyncio
import logging

import aiohttp

import config

_DEEPL_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_TIMEOUT = 15   # seconds per request; the failure path returns None

# DeepL target codes differ slightly from the bot's internal codes.
_DEEPL_TARGET = {
    "EN": "EN-US",
    "PT": "PT-PT",
    "ZH-CN": "ZH",
    "ZH": "ZH",
}


async def deepl_translate(text: str, target: str) -> str | None:
    """Translate via DeepL. Returns None if no key is set or on any failure
    (timeout, connection error, non-200 status, malformed body)."""
    key = config.DEEPL_API_KEY
    if not key:
        return None
    tgt = _DEEPL_TARGET.get(target.upper(), target.upper())
    try:
        timeout = aiohttp.ClientTimeout(total=DEEPL_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                _DEEPL_URL,
                headers={"Authorization": "DeepL-Auth-Key " + key},
                data={"text": text, "target_lang": tgt},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logging.warning(f"DeepL failed ({resp.status}): {body[:200]}")
                    return None
                payload = await resp.json()
    except asyncio.TimeoutError:
        logging.warning(f"DeepL request timed out after {DEEPL_TIMEOUT}s")
        return None
    except Exception as e:
        logging.warning(f"DeepL request error: {e}")
        return None

    try:
        return payload["translations"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logging.warning("DeepL returned an unexpected body")
        return None
