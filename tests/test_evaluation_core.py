from __future__ import annotations

import json
from pathlib import Path

from black_engine.evaluation.models import GameRecord, RuntimeCounters
from black_engine.evaluation.official_runner import legal_selection, summarize
from black_engine.evaluation.promotion import evaluate_promotion
from black_engine.evaluation.replay_judge import audit_episode
from black_engine.evaluation.statistics import wilson_interval
from black_engine.evaluation.taxonomy import canonical_failure_counts
from black_engine.rocket_mewtwo_worldline import SPIDOPS, SPIDOPS_ROCKET_RUSH


def pokemon(cid, serial, hp, max_hp, energies=()):
    return {
        "id": cid,
        "serial": serial,
        "hp": hp,
        "maxHp": max_hp,
        "energyCards": [{"id": energy, "serial": serial * 100 + i} for i, energy in enumerate(energies)],
    }


def clean_replay_summary():
    return {
        "candidate_bundle_sha256": "candidate",
        "corpus_id": "postfix-holdout-001",
        "corpus_kind": "POST_FIX_HOLDOUT",
        "training_corpus_sha256": "a" * 64,
        "training_overlap": [],
        "episodes": 5,
        "episode_ids": [1, 2, 3, 4, 5],
        "source_sha256": [f"{value:064x}" for value in range(1, 6)],
        "fatal": 0,
        "canonical_failure_counts": {
            "LETHAL_MISS": 0,
            "BAD_SPREAD_TARGET": 0,
            "ENERGY_ATTACH_ERROR": 0,
            "TERMINAL_MISS": 0,
            "PROMOTION_ERROR": 0,
        },
        "classifier_support": {
            "LETHAL_MISS": "BUILT_IN",
            "ENERGY_ATTACH_ERROR": "BUILT_IN_ROCKET_MEWTWO",
            "TERMINAL_MISS": "BUILT_IN",
            "PROMOTION_ERROR": "BUILT_IN",
        },
    }


def promotion_config(**extra):
    value = {
        "candidate_bundle_sha256": "candidate",
        "engine_sha256": "engine",
        "training_corpus_sha256": "a" * 64,
        "minimum_runtime_completed": 2,
        "required_replay_taxonomy": list(clean_replay_summary()["canonical_failure_counts"]),
        "replay_taxonomy_applicability": {
            "LETHAL_MISS": "REQUIRED",
            "BAD_SPREAD_TARGET": "NOT_APPLICABLE_ROCKET_MEWTWO_FIXED_DECK_HAS_NO_SPREAD_TARGET_ACTION",
            "ENERGY_ATTACH_ERROR": "REQUIRED",
            "TERMINAL_MISS": "REQUIRED",
            "PROMOTION_ERROR": "REQUIRED",
        },
        "required_replay_corpus_kind": "POST_FIX_HOLDOUT",
    }
    value.update(extra)
    return value


def matchup_config(strength: str = "PROMOTION"):
    return {
        "minimum_games": 2,
        "minimum_win_rate": 0.5,
        "minimum_wilson_low": 0.0,
        "bundle_sha256": "opponent",
        "strength_evidence": strength,
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
    summary = summarize("mirror", records, engine_sha256="engine")
    assert summary.games == 4
    assert summary.seat0_games == summary.seat1_games == 2
    assert summary.wins == summary.losses == 2
    assert summary.runtime.completed == 4
    assert summary.candidate_bundle_sha256 == "a"
    assert summary.opponent_bundle_sha256 == "b"
    assert summary.engine_sha256 == "engine"


def test_promotion_gate_fails_closed_when_matchup_missing():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    assert evaluate_promotion(manifest, {}).verdict == "HOLD"


def _clean_summary(matchup: str = "grim"):
    return {
        "games": 2,
        "seat0_games": 1,
        "seat1_games": 1,
        "win_rate": 1.0,
        "wilson_low": 0.34,
        "evidence_mode": "PROMOTION",
        "runtime": RuntimeCounters(completed=2).__dict__,
        "matchup": matchup,
        "candidate_bundle_sha256": "candidate",
        "opponent_bundle_sha256": "opponent",
        "engine_sha256": "engine",
    }


def test_promotion_gate_passes_only_clean_promotion_evidence():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    verdict = evaluate_promotion(manifest, {"grim": _clean_summary()}, clean_replay_summary())
    assert verdict.verdict == "PROMOTE"
    assert verdict.passed


def test_promotion_gate_requires_only_explicit_core_pool():
    manifest = {
        "promotion": promotion_config(required_matchups=["core"]),
        "matchups": {
            "core": matchup_config(),
            "optional": {"minimum_games": 200, "minimum_win_rate": 1.0, "minimum_wilson_low": 1.0},
        },
    }
    assert evaluate_promotion(manifest, {"core": _clean_summary("core")}, clean_replay_summary()).verdict == "PROMOTE"


def test_promotion_gate_rejects_stress_only_opponent_as_strength_proof():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config("STRESS_ONLY")}}
    assert evaluate_promotion(manifest, {"grim": _clean_summary()}, clean_replay_summary()).verdict == "HOLD"


def test_promotion_gate_rejects_training_replay_as_holdout():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    replay = clean_replay_summary()
    replay["corpus_kind"] = "TRAINING_REPLAY"
    assert evaluate_promotion(manifest, {"grim": _clean_summary()}, replay).verdict == "HOLD"


def test_promotion_gate_rejects_training_overlap_even_when_mislabeled():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    replay = clean_replay_summary()
    replay["training_overlap"] = [replay["source_sha256"][0]]
    assert evaluate_promotion(manifest, {"grim": _clean_summary()}, replay).verdict == "HOLD"


def test_promotion_gate_rejects_replay_from_different_candidate():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    replay = clean_replay_summary()
    replay["candidate_bundle_sha256"] = "different"
    assert evaluate_promotion(manifest, {"grim": _clean_summary()}, replay).verdict == "HOLD"


def _episode_for_observation(obs: dict, action: list[int]) -> dict:
    return {
        "info": {"EpisodeId": 1, "Agents": [{"Name": "ジェニファー"}, {"Name": "red"}]},
        "rewards": [-1, 1],
        "steps": [
            [{"action": [], "status": "ACTIVE", "observation": obs}, {"action": [], "status": "INACTIVE", "observation": {"select": None}}],
            [{"action": action, "status": "INACTIVE", "observation": {"select": None}}, {"action": [], "status": "ACTIVE", "observation": {"select": None}}],
        ],
    }


def _spidops_attack_observation(our_prizes: int) -> dict:
    return {
        "current": {
            "yourIndex": 0,
            "turn": 19,
            "players": [
                {
                    "active": [pokemon(SPIDOPS, 20, 130, 130, (1, 1, 1, 1))],
                    "bench": [pokemon(431, 21, 280, 280), pokemon(414, 22, 120, 120), pokemon(400, 23, 50, 50)],
                    "hand": [],
                    "discard": [],
                    "prize": [None] * our_prizes,
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


def test_replay_judge_detects_terminal_attack_miss(tmp_path: Path):
    path = tmp_path / "episode.json"
    path.write_text(json.dumps(_episode_for_observation(_spidops_attack_observation(2), [0])), encoding="utf-8")
    audit = audit_episode(path, "ジェニファー")
    assert audit.metadata["finding_counts"]["TERMINAL_ACTION_MISS"] == 1
    assert audit.metadata["canonical_failure_counts"]["TERMINAL_MISS"] == 1
    assert "BAD_SPREAD_TARGET" not in audit.metadata["classifier_support"]
    assert audit.overall_score == 75.0


def test_replay_judge_detects_nonterminal_lethal_miss(tmp_path: Path):
    path = tmp_path / "episode.json"
    path.write_text(json.dumps(_episode_for_observation(_spidops_attack_observation(3), [0])), encoding="utf-8")
    audit = audit_episode(path, "ジェニファー")
    assert audit.metadata["finding_counts"]["LETHAL_ACTION_MISS"] == 1
    assert audit.metadata["canonical_failure_counts"]["LETHAL_MISS"] == 1


def test_canonical_taxonomy_preserves_required_zero_categories():
    counts = canonical_failure_counts(["LETHAL_ACTION_MISS", "TERMINAL_ACTION_MISS", "PRIZE_AWARE_ACTIVE_MISS", "ENERGY_ATTACH_SUBOPTIMAL", "SPREAD_TARGET_REGRET"])
    assert counts == {
        "LETHAL_MISS": 1,
        "BAD_SPREAD_TARGET": 1,
        "ENERGY_ATTACH_ERROR": 1,
        "TERMINAL_MISS": 1,
        "PROMOTION_ERROR": 1,
    }


def test_red_team_profiles_are_replay_grounded_subset_and_decks_are_exact_60():
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads((root / "red_team" / "profiles.json").read_text(encoding="utf-8"))
    sources = json.loads((root / "red_team" / "replay_sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "red_team" / "manifest.json").read_text(encoding="utf-8"))
    fidelity = json.loads((root / "red_team" / "fidelity_baseline.json").read_text(encoding="utf-8"))
    assert set(profiles) == set(sources)
    assert set(profiles).issubset(set(manifest["matchups"]))
    assert fidelity["strength_evidence"] == "STRESS_ONLY"
    for slug in profiles:
        deck = [int(value) for value in (root / "red_team" / "decks" / f"{slug}.csv").read_text().splitlines() if value]
        assert len(deck) == 60


def test_replay_grounded_grimmsnarl_prefers_shadow_bullet():
    from red_team.replay_grounded_agent import ReplayGroundedPolicy
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads((root / "red_team" / "profiles.json").read_text(encoding="utf-8"))
    deck = [int(value) for value in (root / "red_team" / "decks" / "grimmsnarl.csv").read_text().splitlines() if value]
    policy = ReplayGroundedPolicy(deck, profiles["grimmsnarl"])
    obs = {
        "current": {
            "yourIndex": 1,
            "turn": 6,
            "players": [
                {"active": [pokemon(431, 1, 280, 280)], "bench": [], "prize": [None] * 6},
                {"active": [pokemon(648, 2, 320, 320, (7, 7))], "bench": [], "prize": [None] * 6},
            ],
        },
        "select": {"context": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 14}, {"type": 13, "attackId": 937}]},
    }
    assert policy.agent(obs) == [1]


def test_bundle_tree_hash_ignores_python_cache(tmp_path: Path):
    from black_engine.evaluation.bundles import tree_sha256
    (tmp_path / "main.py").write_text("x=1\n")
    before = tree_sha256(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-312.pyc").write_bytes(b"generated")
    assert tree_sha256(tmp_path) == before


def test_promotion_gate_fails_closed_without_postfix_replay_summary():
    manifest = {"promotion": promotion_config(), "matchups": {"grim": matchup_config()}}
    assert evaluate_promotion(manifest, {"grim": _clean_summary()}, None).verdict == "HOLD"
