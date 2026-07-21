import pytest

from black_engine.dragapult_policy import DragapultCinderacePolicy
from black_engine.factory import SUPPORTED_CANDIDATES, build_candidate_base_policy
from black_engine.mewtwo_policy import MewtwoChampionshipPolicy
from black_lab import GarchompSpiritombPolicy


def test_candidate_policy_factory_dispatches_all_three_production_families():
    assert SUPPORTED_CANDIDATES == (
        "mewtwo_spidops",
        "garchomp_spiritomb",
        "dragapult_cinderace",
    )
    assert isinstance(build_candidate_base_policy("mewtwo_spidops"), MewtwoChampionshipPolicy)
    assert isinstance(build_candidate_base_policy("garchomp_spiritomb"), GarchompSpiritombPolicy)
    assert isinstance(build_candidate_base_policy("dragapult_cinderace"), DragapultCinderacePolicy)


def test_candidate_policy_factory_fails_closed_for_unknown_candidate():
    with pytest.raises(ValueError, match="unknown candidate"):
        build_candidate_base_policy("unknown")
