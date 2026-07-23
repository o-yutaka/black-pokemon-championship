from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_promotion_sources_are_exact_frozen_submission_commits():
    sources = json.loads((ROOT / "red_team" / "promotion_sources.json").read_text(encoding="utf-8"))
    assert set(sources) == {"dragapult_cinderace", "mewtwo_mirror"}
    assert sources["dragapult_cinderace"]["commit_sha"] == "51a98e353abf257e91c3dccbd14a188baddf73f6"
    assert sources["mewtwo_mirror"]["commit_sha"] == "db4eb14b881e96b3f9b2599ea4c9a5e31c1dbc20"
    for source in sources.values():
        assert source["source_type"] == "git_submission_commit"
        assert source["builder_path"] == "scripts/build_submission.py"
        assert source["evidence_identity"] == "FROZEN_BLACK_EXECUTABLE_BUNDLE"
        assert len(source["commit_sha"]) == 40


def test_manifest_binds_promotion_source_without_promoting_reconstructions():
    manifest = json.loads((ROOT / "red_team" / "manifest.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "red_team" / "promotion_sources.json").read_text(encoding="utf-8"))
    for slug, config in manifest["matchups"].items():
        if slug in sources:
            assert config["strength_evidence"] == "PROMOTION"
            assert config["promotion_source"] == sources[slug]
        else:
            assert config["strength_evidence"] == "STRESS_ONLY"
            assert "promotion_source" not in config


def test_locked_mirror_deck_is_the_independent_xerosic_challenger():
    deck = [int(value) for value in (ROOT / "red_team" / "decks" / "mewtwo_mirror.csv").read_text().splitlines() if value]
    assert len(deck) == 60
    assert deck.count(1197) == 2  # Xerosic's Machinations
    assert deck.count(431) == 2
    assert deck.count(15) == 4


def test_runner_preserves_manifest_evidence_mode():
    source = (ROOT / "scripts" / "run_official_red_team.py").read_text(encoding="utf-8")
    assert 'evidence_mode=str(config.get("strength_evidence", "STRESS_ONLY"))' in source
