"""Official cabt engine integration for the isolated BLACK championship lab."""

from .official_runtime import (
    EngineUnavailable,
    OfficialEngineProvenance,
    locate_cg_dir,
    load_official_game,
    run_battle,
)

__all__ = [
    "EngineUnavailable",
    "OfficialEngineProvenance",
    "locate_cg_dir",
    "load_official_game",
    "run_battle",
]
