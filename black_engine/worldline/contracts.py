from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransitionContract:
    expected_context: int | None = None
    expected_option_type: int | None = None
    expected_card_id: int | None = None
    expected_target_serial: int | None = None

    def matches(self, *, context: int | None, option_type: int | None, card_id: int | None, target_serial: int | None) -> bool:
        checks = (
            self.expected_context is None or self.expected_context == context,
            self.expected_option_type is None or self.expected_option_type == option_type,
            self.expected_card_id is None or self.expected_card_id == card_id,
            self.expected_target_serial is None or self.expected_target_serial == target_serial,
        )
        return all(checks)
