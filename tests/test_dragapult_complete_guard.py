from black_engine.dragapult_complete_guards import CompleteDuskBlastGuard
from black_engine.truth import LegalOption, PlayerView, PokemonView, TruthState


def _pokemon(card_id: int, remaining: int, maximum: int, energies=()) -> PokemonView:
    return PokemonView(
        card_id=card_id,
        damage=maximum - remaining,
        max_hp=maximum,
        energy_ids=tuple(energies),
    )


def _player(index: int, *, active=(), bench=()) -> PlayerView:
    return PlayerView(
        index=index,
        active=tuple(active),
        bench=tuple(bench),
        hand_ids=(),
        hand_count=0,
        discard_ids=(),
        prize_ids=(None,) * 6,
        deck_count=40,
        supporter_played=False,
        retreated=False,
        energy_attached=False,
    )


def _truth(me: PlayerView, opponent: PlayerView, option: LegalOption) -> TruthState:
    return TruthState(
        actor=0,
        turn=3,
        result=-1,
        players=(me, opponent),
        options=(option,),
        min_count=1,
        max_count=1,
        select_type=0,
        select_context=0,
        logs=(),
        raw_observation={},
    )


def test_nonterminal_cursed_blast_is_hard_rejected_without_complete_route():
    option = LegalOption(0, 10, 132, 132, -1, "", {})
    truth = _truth(
        _player(0, active=(_pokemon(132, 90, 90),)),
        _player(1, active=(_pokemon(431, 280, 280),)),
        option,
    )
    vote = CompleteDuskBlastGuard().evaluate(truth, option)
    assert vote.hard_reject


def test_cursed_blast_is_admitted_for_direct_prize():
    option = LegalOption(0, 10, 133, 133, -1, "", {})
    truth = _truth(
        _player(0, active=(_pokemon(133, 160, 160),)),
        _player(1, active=(_pokemon(431, 280, 280),), bench=(_pokemon(121, 120, 320),)),
        option,
    )
    vote = CompleteDuskBlastGuard().evaluate(truth, option)
    assert not vote.hard_reject
    assert vote.bonus > 0


def test_cursed_blast_is_admitted_for_immediate_dragapult_conversion():
    option = LegalOption(0, 10, 132, 132, -1, "", {})
    truth = _truth(
        _player(
            0,
            active=(_pokemon(132, 90, 90),),
            bench=(_pokemon(121, 320, 320, energies=(2, 5)),),
        ),
        _player(1, active=(_pokemon(431, 230, 280),)),
        option,
    )
    vote = CompleteDuskBlastGuard().evaluate(truth, option)
    assert not vote.hard_reject
    assert vote.bonus > 0
