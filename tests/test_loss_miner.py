from __future__ import annotations

import json
from pathlib import Path

from black_engine.evaluation.loss_miner import (
    FINDING_TO_LOSS_MODE,
    LOSS_MODES,
    LossModeCase,
    LossModeReport,
    aggregate_reports,
    mine_episode,
)
from black_engine.rocket_mewtwo_worldline import (
    ARTICUNO,
    MEWTWO_EX,
    MURKROW,
    SPIDOPS,
    SPIDOPS_ROCKET_RUSH,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
)

GRIMMSNARL_EX = 648
MIMIKYU = 434


def pokemon(cid, serial, hp, max_hp, energies=()):
    return {
        "id": cid,
        "serial": serial,
        "hp": hp,
        "maxHp": max_hp,
        "energyCards": [
            {"id": energy, "serial": serial * 100 + index}
            for index, energy in enumerate(energies)
        ],
    }


def test_loss_mode_contract_covers_all_five_known_routes():
    assert set(LOSS_MODES) == {
        "MEWTWO_SETUP_DELAY",
        "NO_BACKUP_AFTER_SPIDOPS",
        "UNREADY_EX_EXPOSED",
        "NONPERSISTENT_DAMAGE_LOOP",
        "DECK_OUT_CLOCK",
    }
    assert FINDING_TO_LOSS_MODE["ATTACK_WITHOUT_BACKUP"] == "NO_BACKUP_AFTER_SPIDOPS"
    assert "PRIZE_AWARE_ACTIVE_MISS" not in FINDING_TO_LOSS_MODE
    assert FINDING_TO_LOSS_MODE["NONPERSISTENT_DAMAGE_REPEAT"] == "NONPERSISTENT_DAMAGE_LOOP"
    assert FINDING_TO_LOSS_MODE["DECK_CLOCK_VIOLATION"] == "DECK_OUT_CLOCK"


def test_miner_detects_turn_closed_before_legal_mewtwo_setup(tmp_path: Path):
    observation = {
        "current": {
            "yourIndex": 0,
            "turn": 5,
            "players": [
                {
                    "active": [pokemon(SPIDOPS, 10, 130, 130, (1,))],
                    "bench": [
                        pokemon(MEWTWO_EX, 20, 280, 280),
                        pokemon(TAROUNTULA, 21, 50, 50),
                        pokemon(ARTICUNO, 22, 120, 120),
                        pokemon(MURKROW, 23, 80, 80),
                    ],
                    "hand": [{"id": TEAM_ROCKET_ENERGY, "serial": 500}],
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 30,
                    "supporterPlayed": False,
                },
                {
                    "active": [pokemon(999, 900, 320, 320)],
                    "bench": [],
                    "handCount": 5,
                    "prize": [None] * 6,
                    "deckCount": 30,
                },
            ],
            "result": -1,
        },
        "select": {
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {
                    "type": 8,
                    "cardId": TEAM_ROCKET_ENERGY,
                    "playerIndex": 0,
                    "inPlayArea": 5,
                    "inPlayIndex": 0,
                },
                {
                    "type": 13,
                    "attackId": SPIDOPS_ROCKET_RUSH,
                    "playerIndex": 0,
                    "inPlayArea": 4,
                    "inPlayIndex": 0,
                },
            ],
        },
    }
    episode = {
        "info": {"EpisodeId": 77, "Agents": [{"Name": "BLACK"}, {"Name": "RED"}]},
        "rewards": [-1, 1],
        "steps": [
            [
                {"action": [], "status": "ACTIVE", "observation": observation},
                {"action": [], "status": "INACTIVE", "observation": {"select": None}},
            ],
            [
                {"action": [1], "status": "INACTIVE", "observation": {"select": None}},
                {"action": [], "status": "ACTIVE", "observation": {"select": None}},
            ],
        ],
    }
    path = tmp_path / "77.json"
    path.write_text(json.dumps(episode), encoding="utf-8")

    report = mine_episode(path, "BLACK")
    cases = [case for case in report.cases if case.loss_mode == "MEWTWO_SETUP_DELAY"]
    assert len(cases) == 1
    assert cases[0].detail_code == "MEWTWO_SETUP_TURN_CLOSED"
    assert cases[0].recorded == [1]
    assert cases[0].expected == [0]
    assert cases[0].evidence["best_setup_plan"] == "FIRST_MEWTWO_READY"


def test_miner_detects_log_grounded_unready_ex_exposure(tmp_path: Path):
    damage_observation = {
        "current": {"yourIndex": 0, "turn": 10, "players": [{}, {}], "result": -1},
        "select": None,
        "logs": [
            {
                "type": 15,
                "playerIndex": 1,
                "cardId": GRIMMSNARL_EX,
                "serial": 90,
                "attackId": 937,
            },
            {
                "type": 16,
                "playerIndex": 0,
                "cardId": SPIDOPS,
                "serial": 7,
                "putDamageCounter": False,
                "value": -180,
            },
        ],
    }
    switch_observation = {
        "current": {
            "yourIndex": 0,
            "turn": 11,
            "players": [
                {
                    "active": [pokemon(MIMIKYU, 10, 60, 60)],
                    "bench": [
                        pokemon(MEWTWO_EX, 20, 170, 280),
                        pokemon(SPIDOPS, 21, 130, 130, (1, 5)),
                        pokemon(ARTICUNO, 22, 120, 120),
                        pokemon(MEWTWO_EX, 23, 170, 280),
                    ],
                    "hand": [],
                    "discard": [],
                    "prize": [None] * 4,
                    "deckCount": 20,
                    "supporterPlayed": False,
                },
                {
                    "active": [pokemon(GRIMMSNARL_EX, 90, 300, 320, (7, 7))],
                    "bench": [],
                    "handCount": 5,
                    "prize": [None] * 2,
                    "deckCount": 20,
                },
            ],
            "result": -1,
        },
        "select": {
            "context": 3,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 3, "area": 5, "index": 0, "playerIndex": 0},
                {"type": 3, "area": 5, "index": 1, "playerIndex": 0},
                {"type": 3, "area": 5, "index": 2, "playerIndex": 0},
                {"type": 3, "area": 5, "index": 3, "playerIndex": 0},
            ],
        },
        "logs": [],
    }
    episode = {
        "info": {"EpisodeId": 88, "Agents": [{"Name": "BLACK"}, {"Name": "RED"}]},
        "rewards": [-1, 1],
        "steps": [
            [
                {"action": [], "status": "INACTIVE", "observation": damage_observation},
                {"action": [], "status": "ACTIVE", "observation": {"select": None}},
            ],
            [
                {"action": [], "status": "ACTIVE", "observation": switch_observation},
                {"action": [], "status": "INACTIVE", "observation": {"select": None}},
            ],
            [
                {"action": [0], "status": "INACTIVE", "observation": {"select": None}},
                {"action": [], "status": "ACTIVE", "observation": {"select": None}},
            ],
        ],
    }
    path = tmp_path / "88.json"
    path.write_text(json.dumps(episode), encoding="utf-8")

    report = mine_episode(path, "BLACK")
    cases = [case for case in report.cases if case.loss_mode == "UNREADY_EX_EXPOSED"]
    assert len(cases) == 1
    assert cases[0].detail_code == "KNOWN_LETHAL_UNREADY_EX_SWITCH"
    assert cases[0].severity == "FATAL"
    assert cases[0].recorded == [0]
    assert cases[0].expected == [1]
    assert cases[0].evidence["observed_damage"] == 180
    assert cases[0].evidence["candidate_card_id"] == MEWTWO_EX


def test_repair_queue_orders_by_accumulated_severity():
    common = dict(
        episode_id=1,
        agent_name="BLACK",
        step=1,
        turn=1,
        recorded=[0],
        expected=None,
        evidence={},
        acceptance="contract",
        confidence=1.0,
    )
    fatal = LossModeCase(
        **common,
        loss_mode="UNREADY_EX_EXPOSED",
        detail_code="KNOWN_LETHAL_UNREADY_EX_SWITCH",
        severity="FATAL",
        policy_hook="FORBID_VOLUNTARY_SWITCH_TO_UNREADY_EX",
    )
    major = LossModeCase(
        **common,
        loss_mode="DECK_OUT_CLOCK",
        detail_code="DECK_CLOCK_VIOLATION",
        severity="MAJOR",
        policy_hook="DECK_CLOCK_SUPPRESS_RESOURCE",
    )
    summary = aggregate_reports([LossModeReport(1, "BLACK", "LOSS", (major, fatal))])
    assert summary["repair_queue"][0]["loss_mode"] == "UNREADY_EX_EXPOSED"
    assert summary["counts"]["DECK_OUT_CLOCK"] == 1
