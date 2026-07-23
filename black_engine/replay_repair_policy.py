from __future__ import annotations

from .championship_policy import ChampionshipRocketMewtwoPolicy as BaseChampionshipPolicy
from .rocket_mewtwo_worldline import T_ATTACK, T_END, T_ENERGY


class ChampionshipRocketMewtwoPolicy(BaseChampionshipPolicy):
    """Replay-repair layer promoted above the tested championship policy.

    A normal Energy attachment does not close the turn. When the official legal
    option list contains both a turn-closing Attack/End and an attachment that
    advances the first or second Mewtwo to attack readiness, choose the setup
    action first. A game-winning attack remains the absolute exception.
    """

    def _mewtwo_setup_before_close(self, context: dict) -> int | None:
        truth = context["truth"]
        if context.get("ready_mewtwo"):
            return None
        if not any(option.action_type in {T_ATTACK, T_END} for option in truth.options):
            return None

        candidates = []
        for option in truth.options:
            if option.action_type != T_ENERGY:
                continue
            result = self._plan_for_option(option.action_index, context)
            if result.illegal:
                continue
            if result.plan.plan_id in {
                "FIRST_MEWTWO_READY",
                "SECOND_MEWTWO_DEVELOPMENT",
            }:
                candidates.append(result)
        if not candidates:
            return None
        return self.judge.choose(candidates).plan.root_action_index

    def choose_single(self, options: list, context: dict) -> int:
        # Never delay a verified game-winning attack.
        if self._terminal_attack(context) is not None:
            return super().choose_single(options, context)

        setup = self._mewtwo_setup_before_close(context)
        if setup is not None:
            self.last_runner_id = "MEWTWO_SETUP_BEFORE_TURN_CLOSE"
            return setup
        return super().choose_single(options, context)
