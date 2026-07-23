from __future__ import annotations

import hashlib
import json
from pathlib import Path

from black_engine import ChampionshipRocketMewtwoPolicy
from black_engine.evaluation.promotion import evaluate_promotion


def _obs(minimum=1, maximum=None):
    return {
        "current": {"yourIndex": 0, "players": [{}, {}]},
        "select": {
            "context": 0,
            "minCount": minimum,
            "maxCount": maximum,
            "option": [{"type": 14}, {"type": 14}, {"type": 14}],
        },
    }


def test_deployed_policy_accepts_null_max_count_as_exact_minimum():
    obs = _obs(minimum=1, maximum=None)
    policy = ChampionshipRocketMewtwoPolicy()
    assert policy.agent(obs) in ([0], [1], [2])


def test_generic_optional_multi_select_uses_minimum_not_maximum():
    obs = _obs(minimum=0, maximum=3)
    policy = ChampionshipRocketMewtwoPolicy()
    assert policy.agent(obs) == []


def test_manifest_freezes_exact_training_corpus_and_all_generated_red_bundles_are_stress_only():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "red_team" / "manifest.json").read_text())
    expected = hashlib.sha256((root / "red_team" / "training_replay_corpus.json").read_bytes()).hexdigest()
    assert manifest["promotion"]["training_corpus_sha256"] == expected
    assert {cfg["strength_evidence"] for cfg in manifest["matchups"].values()} == {"STRESS_ONLY"}


def test_promotion_rejects_different_training_corpus_sha():
    manifest = {
        "promotion": {
            "required_matchups": [],
            "minimum_runtime_completed": 0,
            "required_replay_taxonomy": ["LETHAL_MISS"],
            "replay_taxonomy_applicability": {"LETHAL_MISS": "REQUIRED"},
            "candidate_bundle_sha256": "c" * 64,
            "engine_sha256": "e" * 64,
            "training_corpus_sha256": "a" * 64,
            "minimum_postfix_replay_episodes": 1,
        },
        "matchups": {},
    }
    replay = {
        "candidate_bundle_sha256": "c" * 64,
        "corpus_kind": "POST_FIX_HOLDOUT",
        "corpus_id": "holdout",
        "training_corpus_sha256": "b" * 64,
        "training_overlap": [],
        "episodes": 1,
        "episode_ids": [1],
        "source_sha256": ["d" * 64],
        "canonical_failure_counts": {"LETHAL_MISS": 0},
        "classifier_support": {"LETHAL_MISS": ["BUILT_IN"]},
        "fatal": 0,
    }
    verdict = evaluate_promotion(manifest, {}, replay)
    check = next(item for item in verdict.checks if item.name == "postfix_replay.training_corpus_sha")
    assert not check.passed
