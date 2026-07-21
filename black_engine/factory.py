from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .belief import ArchetypeTemplate, BayesianBeliefModel
from .hybrid import HybridPolicy
from .rl_prior import TabularQPrior

SUPPORTED_CANDIDATES = (
    "mewtwo_spidops",
    "garchomp_spiritomb",
    "dragapult_cinderace",
    "crustle_redteam",
    "grimmsnarl_redteam",
)


def build_candidate_base_policy(candidate: str):
    """Build the exact base policy used by a candidate production entrypoint.

    Candidate policies do not share one implementation family. Mewtwo has its
    championship policy, Dragapult has the complete engine-source policy layer,
    and Garchomp/Red-Team candidates use the legacy black_lab dispatcher. All
    runners and candidate entrypoints call this function so no candidate can
    silently fall through to the wrong policy family.
    """
    if candidate == "mewtwo_spidops":
        from .mewtwo_policy import build_mewtwo_policy

        return build_mewtwo_policy()
    if candidate == "dragapult_cinderace":
        from .dragapult_championship_policy import DragapultChampionshipPolicy

        return DragapultChampionshipPolicy()
    if candidate in ("garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam"):
        from black_lab import build_policy

        return build_policy(candidate)
    raise ValueError(
        f"unknown candidate: {candidate}; supported={','.join(SUPPORTED_CANDIDATES)}"
    )


def _load_templates(path: str | Path | None) -> tuple[ArchetypeTemplate, ...]:
    if path is None or not Path(path).is_file():
        return ()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("templates") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("belief bank must be a list or {'templates': [...]} object")
    return tuple(
        ArchetypeTemplate(
            name=str(row["name"]),
            deck=tuple(int(card) for card in row["deck"]),
            prior=float(row.get("prior", 1.0)),
        )
        for row in rows
    )


def _build_ismcts(belief: BayesianBeliefModel):
    if not belief.templates or os.environ.get("BLACK_ISMCTS", "1") in {"0", "false", "False"}:
        return None
    try:
        from .cabt_adapter import CabtSearchAdapter
        from .ismcts import InformationSetMCTS

        adapter = CabtSearchAdapter(os.environ.get("CABT_CG_DIR"))
        return InformationSetMCTS(
            adapter,
            belief,
            simulations=int(os.environ.get("BLACK_ISMCTS_SIMS", "48")),
            time_budget_ms=float(os.environ.get("BLACK_ISMCTS_MS", "35")),
            rollout_depth=int(os.environ.get("BLACK_ISMCTS_DEPTH", "8")),
        )
    except Exception:
        return None


def build_hybrid_policy(
    candidate: str,
    base_policy: Any,
    *,
    root: str | Path | None = None,
    ismcts=None,
) -> HybridPolicy:
    project_root = Path(root) if root else Path(__file__).resolve().parents[1]
    belief_path = os.environ.get("BLACK_BELIEF_BANK")
    if not belief_path:
        default = project_root / "models" / "opponent_belief_bank.json"
        belief_path = str(default) if default.is_file() else None
    belief = BayesianBeliefModel(_load_templates(belief_path))
    rl_path = project_root / "models" / f"rl_prior_{candidate}.json"
    return HybridPolicy(
        candidate,
        base_policy,
        belief=belief,
        rl_prior=TabularQPrior.load(rl_path),
        ismcts=ismcts if ismcts is not None else _build_ismcts(belief),
    )
