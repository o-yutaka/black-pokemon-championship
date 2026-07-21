# Deck Audit Checklist

Every production deck change must pass all checks below before merge.

1. Exact 60-card multiset is locked in a regression test.
2. Every card ID resolves to the intended card identity.
3. Copy limits and ACE SPEC count pass.
4. Pokémon evolution lines are internally reachable.
5. Search cards have real targets in the deck.
6. Energy types satisfy every declared attack and acceleration route.
7. Policy constants and deck IDs are identical.
8. Deck identity is distinguished from older candidate variants.
9. Static correctness is not reported as performance evidence.
10. Any card-count change requires paired official-engine evaluation.
