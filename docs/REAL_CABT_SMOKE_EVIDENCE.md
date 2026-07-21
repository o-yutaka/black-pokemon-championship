# Real cabt Smoke Evidence

## HEAD

`12fb3e75a6a36d0922b6b1a932c983e8d7f3a96d`

## Verified against the real local cabt engine

- Hybrid entrypoints are actually wired.
- ISMCTS / Bayesian belief / RL prior orchestration completed six smoke games without a crash before the base-policy contract correction.
- The corrected base policy subsequently completed ten of ten self-play smoke games without a crash.
- GitHub Actions static candidate gate and pytest pass on this exact HEAD.

## Corrected engine-wire assumptions

Real cabt options identify cards by board references rather than embedded card names or IDs:

- `area` / `index`
- `inPlayArea` / `inPlayIndex`
- `playerIndex`
- `attackId`

Resolved `AreaType` values:

- `2`: hand
- `3`: discard
- `4`: active
- `5`: bench
- `6`: prize

In-play Pokémon expose:

- `hp`: current remaining HP
- `maxHp`: maximum HP

Therefore:

```text
damage = maxHp - hp
remaining HP = hp
```

Attack selection uses official `attackId` values rather than absent display labels:

- Garchomp ex Corkscrew Dive: `531`
- Garchomp ex Draconic Buster: `532`
- Murkrow Deceit: `652`
- Murkrow Torment: `653`

## Measured resolution improvement

- Before correction: `option_card_id` resolved `0 / 734` observed options.
- After correction: `538 / 887` observed options; the unresolved remainder are card-less option types such as End Turn.
- Text labels were absent in `0 / 1382` observed cases, confirming that label-based attack dispatch was invalid.

## Verdict

```black
REAL_CABT_WIRING PASS
HYBRID_SMOKE_6 PASS_NO_CRASH
CORRECTED_SELF_PLAY_10 PASS_NO_CRASH
CARD_REFERENCE_RESOLUTION PASS
HP_CONTRACT PASS
GITHUB_ACTIONS PASS
WIN_RATE UNVERIFIED
MERGE HOLD_PERFORMANCE
END
```

Crash-free smoke proves runtime compatibility, not strength. Promotion requires larger alternating-seat evaluation and deterministic-base ablation.
