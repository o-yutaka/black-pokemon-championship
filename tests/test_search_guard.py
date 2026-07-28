from black_engine.search_guard import choose_search_safe_single, rejected_option_indexes


def test_rejected_option_indexes_accepts_only_official_search_cycles():
    overlay = {
        "rejectedBranches": [
            {
                "optionIndex": 2,
                "reason": "RESOURCE_LOSS_CYCLE",
                "source": "cg.api.search_step",
                "killedBy": "OfficialSearchCycleGuard",
            },
            {
                "optionIndex": 3,
                "reason": "RESOURCE_LOSS_CYCLE",
                "source": "ScoredPolicy.choose_single",
                "killedBy": "SwitchLoopPolicy",
            },
            {
                "optionIndex": 4,
                "reason": "ENERGY_WRONG_TARGET",
                "source": "cg.api.search_step",
                "killedBy": "OfficialSearchCycleGuard",
            },
        ]
    }
    assert rejected_option_indexes(overlay) == {2}


def test_choose_search_safe_single_uses_highest_scoring_unblocked_option():
    assert choose_search_safe_single([2], [10.0, 40.0, 100.0, 30.0], {2, 3}) == [1]


def test_choose_search_safe_single_preserves_unblocked_and_multi_select():
    assert choose_search_safe_single([1], [10.0, 40.0, 100.0], {2}) == [1]
    assert choose_search_safe_single([0, 1], [10.0, 40.0], {0}) == [0, 1]


def test_choose_search_safe_single_preserves_original_when_all_blocked():
    assert choose_search_safe_single([0], [10.0, 20.0], {0, 1}) == [0]
