"""Check generated output against a configured denylist.

Read config.BLOCKLIST_FILE, one term per line with # comments.
With no file present, is_clean() returns True."""

import logging
import re

import config

_terms = None


def _collapse(s: str) -> str:
    """Lowercase and remove characters outside [a-z0-9] before substring matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _load():
    global _terms
    if _terms is None:
        terms = set()
        try:
            # utf-8-sig: a BOM would otherwise glue to the first '#' and turn that
            # comment line into a live blocked term
            with open(config.BLOCKLIST_FILE, encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        c = _collapse(line)
                        if c:
                            terms.add(c)
        except FileNotFoundError:
            logging.info("output_filter: no blocklist file; nothing is filtered.")
        _terms = terms
    return _terms


def is_clean(text: str) -> bool:
    """True if text contains no denylisted term (evasion-collapsed substring)."""
    collapsed = _collapse(text)
    if not collapsed:
        return True
    return not any(term in collapsed for term in _load())


def active() -> bool:
    """Whether a non-empty denylist is loaded."""
    return len(_load()) > 0
