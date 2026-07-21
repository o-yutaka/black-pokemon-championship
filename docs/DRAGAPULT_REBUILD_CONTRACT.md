# BLACK Dragapult Repository Rebuild Contract

## Verdict

This branch is one production submission for one fixed deck:

`dragapult_cinderace`

Mewtwo, Garchomp, Crustle, Grimmsnarl, and every future deck are forbidden from the production factory, root entrypoint, root deck, package builder, and submission archive.

## Canonical production files

```text
main.py
deck.csv
submission_contract.py
black_lab.py
black_engine/
```

The packaged archive adds the official `cg/` directory but does not generate or rewrite `main.py` or `deck.csv`.

## Single-deck law

1. `factory.CANDIDATE` is exactly `dragapult_cinderace`.
2. `SUPPORTED_CANDIDATES` contains exactly one value.
3. Requests for another candidate fail before policy construction.
4. Root `deck.csv` and `candidates/dragapult_cinderace/deck.csv` must be byte-identical.
5. Root `main.py` loads only `dragapult_cinderace`.
6. Submission packaging is byte-preserving.
7. Opponent decks belong to evaluation data, never the production factory.
8. Historical mixed branches and PRs are evidence only and must never be merged.

## Frozen final deck identity

- Cinderace: 1-0-4
- Dragapult: 4-4-3
- Dusknoir: 3-2-2
- Azelf: 2
- Fire Energy: 6
- Psychic Energy: 7
- Total: 60

## Required gates

```text
SOURCE_LAYOUT
DECK_60
ROOT_CANDIDATE_BYTE_IDENTITY
SINGLE_FACTORY_CANDIDATE
NON_DRAGAPULT_FACTORY_REJECT
SUBMISSION_STAGE_BYTE_IDENTITY
ISOLATED_IMPORT
OFFICIAL_CG_SMOKE
```

Performance claims remain forbidden until official-engine evaluation on the exact head.
