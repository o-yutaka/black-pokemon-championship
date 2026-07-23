from __future__ import annotations

import sys


MESSAGE = """LEGACY EVALUATION DISABLED

This script used deterministic_fallback as the opponent and cannot produce
runtime, matchup, or promotion evidence. It is intentionally fail-closed.

Use:
  python scripts/run_official_red_team.py \\
    --cg-dir <official-cg-dir> \\
    --candidate-bundle <exact-candidate-bundle>

Both seats must run real fixed Bundles on the official cg/libcg.so engine.
"""


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
