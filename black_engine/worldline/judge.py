from __future__ import annotations

from .model import WorldlineResult


class CausalJudge:
    """Lexicographic judge for coherent candidate plans."""

    @staticmethod
    def key(result: WorldlineResult) -> tuple:
        return (
            not result.illegal,
            not result.immediate_loss,
            result.guaranteed_win,
            result.prevents_forced_loss,
            -result.our_attacks_to_win,
            result.opponent_attacks_to_win,
            result.hostile_survival,
            -result.irreversible_cost,
            result.opponent_pain,
            -result.regret,
            result.confidence,
            -result.plan.root_action_index,
        )

    def choose(self, results: list[WorldlineResult]) -> WorldlineResult:
        if not results:
            raise ValueError("no worldline results")
        return max(results, key=self.key)
