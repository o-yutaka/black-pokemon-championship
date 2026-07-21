# Dragapult Deck Audit v1

## Verdict

`STATIC_CONTENT_PASS / POLICY_IDENTITY_PASS / PERFORMANCE_HOLD`

This audit verifies the exact deck merged into `main`. It does not change `deck.csv` and does not claim competitive superiority.

## Canonical 60-card identity

### Pokémon — 25

| Card ID | Card | Count |
|---:|---|---:|
| 151 | Scorbunny | 1 |
| 666 | Cinderace | 4 |
| 119 | Dreepy | 4 |
| 120 | Drakloak | 4 |
| 121 | Dragapult ex | 3 |
| 131 | Duskull | 3 |
| 132 | Dusclops | 2 |
| 133 | Dusknoir | 2 |
| 217 | Azelf | 2 |

### Trainers — 22

| Card ID | Card | Count |
|---:|---|---:|
| 1086 | Buddy-Buddy Poffin | 4 |
| 1079 | Rare Candy | 3 |
| 1127 | Tera Orb | 2 |
| 1152 | Poké Pad | 1 |
| 1097 | Night Stretcher | 2 |
| 1123 | Switch | 1 |
| 1088 | Prime Catcher | 1 |
| 1231 | Dawn | 3 |
| 1198 | Crispin | 2 |
| 1227 | Lillie's Determination | 2 |
| 1182 | Boss's Orders | 1 |

### Energy — 13

| Card ID | Card | Count |
|---:|---|---:|
| 2 | Basic Fire Energy | 6 |
| 5 | Basic Psychic Energy | 7 |

## Static contract checks

- Total cards: 60 — PASS
- Copy limit: PASS
- ACE SPEC: Prime Catcher exactly 1 — PASS
- Dragapult line: 4-4-3 — PASS
- Dusknoir line: 3-2-2 — PASS
- Cinderace: 4 copies with Scorbunny 1 — PASS as the declared setup-focused design
- Azelf: 2 — PASS
- Fire/Psychic energy: 6/7 — PASS
- `black_engine/policy.py` card IDs match every card used by the deck — PASS
- Poffin can search all four Basic Pokémon identities in this deck because each has 70 HP or less — PASS
- Tera Orb searches Dragapult ex; Poké Pad searches the non-Rule-Box Pokémon; Dawn covers Basic/Stage 1/Stage 2 development — PASS

## Important interpretation

This is the **4-4-3 cleanroom variant**. It is not the earlier A6 list and not the earlier BLACK-C1 4-2-4 list.

The merged deck deliberately uses:

- four Drakloak for Recon Directive and a non-Candy evolution path;
- three Dragapult ex rather than four;
- one Scorbunny and four Cinderace to maximize opening Explosiveness while retaining one Rare Candy recovery route;
- thirteen Energy at 6 Fire / 7 Psychic.

## Risks that require measured evaluation

### 1. Cinderace dead-card concentration

Four Cinderace maximize the chance of opening one, but only one Scorbunny and no Raboot exist. A Cinderace drawn after setup is usable only through the single Scorbunny plus Rare Candy route. This is intentional but high-risk and must be measured rather than assumed correct.

Opening-hand reference, using a seven-card hypergeometric calculation:

- at least one Cinderace: approximately 39.95%;
- at least one ordinary Basic Pokémon: approximately 74.14%;
- at least one ordinary Basic or Cinderace setup card: approximately 86.14%;
- theoretical no-setup hand: approximately 13.86%, assuming Explosiveness is accepted as setup eligibility.

### 2. Shared Rare Candy pressure

Three Rare Candy are shared by Dragapult, Dusknoir, and the non-opening Cinderace route. The deck also carries four Drakloak and two Dusclops, which reduce but do not remove that contention.

### 3. Energy count

The list uses 6 Fire / 7 Psychic. This is one fewer Psychic Energy than the earlier 6/8 A6 concept. Static legality cannot prove that 7 Psychic is sufficient for two Dragapult plus Azelf routes.

## Promotion rule

Do not change the deck from this audit alone.

A card-count change requires paired official-engine evidence with:

- identical agent version;
- identical opponent Bundles;
- alternating seats and paired seeds;
- setup failure, first attack turn, second Dragapult readiness, Fire starvation, Psychic starvation, dead Cinderace draw rate, errors, illegal actions and timeouts reported separately.

Until that evidence exists, the correct verdict is:

`DECK_IDENTITY_CONFIRMED / PERFORMANCE_UNVERIFIED / NO_DECK_MUTATION`
