# Deck Audit Scope

This change audits and locks the existing production deck. It does not alter `deck.csv`, policy behavior, runtime behavior, or submission packaging.

Merge is permitted only when CI passes and the exact deck fingerprint test succeeds.
