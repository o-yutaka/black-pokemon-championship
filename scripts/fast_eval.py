from __future__ import annotations

import sys


MESSAGE = """LEGACY FAST EVAL DISABLED

This path delegated to worker_eval.py and measured a real candidate against a
deterministic fallback opponent. Such results are prohibited as BLACK strength
or promotion evidence.

Use scripts/run_official_red_team.py with exact fixed candidate/opponent
Bundles and the official cg/libcg.so engine.
"""


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
