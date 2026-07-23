from __future__ import annotations

import json
from pathlib import Path

from black_engine.evaluation.models import GameRecord, RuntimeCounters
from black_engine.evaluation.official_runner import legal_selection, summarize
from black_engine.evaluation.promotion import evaluate_promotion
from black_engine.evaluation.replay_judge import audit_episode
from black_engine.evaluation.statistics import wilson_interval
from black_engine.rocket_mewtwo_worldline import SPIDOPS, SPIDOPS_ROCKET_RUSH


def pokemon(cid, serial, hp, max_hp, energies=()):
    return {
        "id": cid,
        "serial": serial,
        "hp": hp,
        "maxHp": max_hp,
        "energyCards": [{"id": energy, "serial": serial * 100 + i} for i, energy in enumerate(energies)],
    }


def test_wilson_interval_is_bounded_and_nontrivial():
    low, high = wilson_interval(50, 100)
    assert 0.39 < low < 0.41
    assert 0.59 < high < 0.61


def test_official_selection_contract_rejects_mandatory_empty_and_bad_indices():
    obs = {"select": {"option": [{"type": 14}], "minCount": 1, "maxCount": 1}}
    assert legal_selection(obs, [0])
    assert not legal_selection(obs, [])
    assert not legal_selection(obs, [1])
    assert not legal_selection(obs, [0, 0])


def test_matchup_summary_is_seat_balanced_and_includes_runtime():
    records = []
    for seat, winner in ((0, 0), (1, 1), (0, 1), (1, 0)):
        records.append(
            GameRecord(
                matchup="mirror",
                candidate_bundle_sha256="a",
                opponent_bundle_sha256="b",
                candidate_seat=seat,
                winner_seat=winner,
                result="DONE",
                steps=10,
                decision_ms=[10.0, 20.0],
                runtime=RuntimeCounters(completed=1),
            )
        )
    summary = summarize("mirror", records)
    assert summary.games == 4
    assert summary.seat0_games == summary.seat1_games == 2
    assert summary.wins == summary.losses == 2
    assert summary.runtime.completed == 4


def test_promotion_gate_fails_closed_when_matchup_missing():
    manifest = {
        "promotion": {"minimum_runtime_completed": 2},
        "matchups": {"grim": {"minimum_games": 2, "minimum_win_rate": 0.5, "minimum_wilson_low": 0.0}},
    }
    assert evaluate_promotion(manifest, {}).verdict == "HOLD"


def test_promotion_gate_passes_only_clean_promotion_evidence():
    manifest = {
        "promotion": {"minimum_runtime_completed": 2},
        "matchups": {"grim": {"minimum_games": 2, "minimum_win_rate": 0.5, "minimum_wilson_low": 0.0}},
    }
    summary = {
        "games": 2,
        "seat0_games": 1,
        "seat1_games": 1,
        "win_rate": 1.0,
        "wilson_low": 0.34,
        "evidence_mode": "PROMOTION",
        "runtime": RuntimeCounters(completed=2).__dict__,
    }
    verdict = evaluate_promotion(manifest, {"grim": summary})
    assert verdict.verdict == "PROMOTE"
    assert verdict.passed


def test_replay_judge_detects_terminal_attack_miss(tmp_path: Path):
    obs = {
        "current": {
            "yourIndex": 0,
            "turn": 19,
            "players": [
                {
                    "active": [pokemon(SPIDOPS, 20, 130, 130, (1, 1, 1, 1))],
                    "bench": [pokemon(431, 21, 280, 280), pokemon(414, 22, 120, 120), pokemon(400, 23, 50, 50)],
                    "hand": [],
                    "discard": [],
                    "prize": [None, None],
                    "deckCount": 10,
                    "supporterPlayed": False,
                },
                {
                    "active": [pokemon(648, 900, 30, 320)],
                    "bench": [],
                    "handCount": 5,
                    "prize": [None, None, None, None],
                    "deckCount": 15,
                },
            ],
            "result": -1,
        },
        "select": {
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 7, "cardId": 1134},
                {"type": 13, "attackId": SPIDOPS_ROCKET_RUSH, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0},
            ],
        },
    }
    episode = {
        "info": {"EpisodeId": 1, "Agents": [{"Name": "ジェニファー"}, {"Name": "red"}]},
        "rewards": [-1, 1],
        "steps": [
            [{"action": [], "status": "ACTIVE", "observation": obs}, {"action": [], "status": "INACTIVE", "observation": {"select": None}}],
            [{"action": [0], "status": "INACTIVE", "observation": {"select": None}}, {"action": [], "status": "ACTIVE", "observation": {"select": None}}],
        ],
    }
    path = tmp_path / "episode.json"
    path.write_text(json.dumps(episode), encoding="utf-8")
    audit = audit_episode(path, "ジェニファー")
    assert audit.metadata["finding_counts"]["TERMINAL_ACTION_MISS"] == 1
    assert audit.overall_score == 75.0
