from behavior_audit import audit_frames


def frame(active, bench=None, events=None, candidates=None, turn=1):
    return {
        "turn": turn,
        "players": [
            {"active": active, "bench": bench or [], "supporterPlayed": False},
            {"active": {"serial": 99, "energies": []}, "bench": []},
        ],
        "events": events or [],
        "decision": {"candidates": candidates or []},
    }


def test_detects_switch_backtrack_loop():
    frames = [
        frame({"serial": 1, "energies": []}),
        frame({"serial": 2, "energies": []}, events=[{"type": "switch", "actor": 0}]),
        frame({"serial": 1, "energies": []}, events=[{"type": "switch", "actor": 0}]),
    ]
    report = audit_frames(frames)
    assert report["gate"] == "HOLD"
    assert "SWITCH_BACKTRACK_LOOP" in {item["code"] for item in report["findings"]}


def test_detects_attack_window_skipped():
    candidates = [
        {"kind": "attack", "selected": False},
        {"kind": "switch", "selected": True},
    ]
    report = audit_frames([
        frame({"serial": 1, "energies": ["P"]}, candidates=candidates),
        frame({"serial": 2, "energies": []}, events=[{"type": "switch", "actor": 0}]),
    ])
    assert "ATTACK_WINDOW_SKIPPED" in {item["code"] for item in report["findings"]}


def test_clean_attack_route_passes():
    candidates = [{"kind": "attack", "selected": True}]
    report = audit_frames([
        frame({"serial": 1, "energies": ["P"]}, candidates=candidates),
        frame({"serial": 1, "energies": ["P"]}, events=[{"type": "attack", "actor": 0}]),
    ])
    assert report["gate"] == "PASS"
    assert report["findingCount"] == 0
