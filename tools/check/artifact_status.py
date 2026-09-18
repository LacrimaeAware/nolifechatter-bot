"""Print generated artifact status without rebuilding anything.

Use this before trusting semantic/persona commands after alias/filter/embedding
changes:

    python tools/check/artifact_status.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# A fresh clone has no config.toml yet; the checks only need the example
# values, so point the loader at config.example.toml unless NLC_CONFIG is set.
if not (ROOT / "config.toml").exists():
    os.environ.setdefault("NLC_CONFIG", str(ROOT / "config.example.toml"))

from utils import artifact_status  # noqa: E402


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    rows = artifact_status.status_rows()
    print(artifact_status.format_table(rows))
    return 1 if any(row["status"] != "ok" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
