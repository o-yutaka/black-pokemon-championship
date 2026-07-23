# BLACK Battle Studio

Replay-first, iPhone-ready battle viewer, deck builder, Kaggle Bundle loader, and local official-engine bridge for the Pokémon TCG AI competition project.

## Scope

- Read-only replay visualization and immutable snapshot truth
- CABT-shaped deterministic emulator
- Local official C++ engine ZIP or Linux `libcg.so` upload
- Official source ZIP → local `g++` C++20 shared-library build
- Kaggle `.tar.gz` / `.tgz` Bundle validation and isolated Agent loading
- Two uploaded Agent Bundles running against the same official engine
- FastAPI HTTP/WebSocket live board updates
- Local card database ingestion and searchable 60-card deck builder
- `deck.csv` export and imported-Bundle deck reflection
- No changes to `submission/`, root `deck.csv`, policy runtime, or official engine files
- Restricted engine/card artifacts remain upload-only and are never committed

## Start the local bridge

```bash
cd tools/battle_studio/frontend
npm install --no-audit --no-fund
npm test
npm run build
cd ../backend
python -m pip install -r requirements-live.txt
python -m uvicorn live_server:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

## Official runtime flow

Use the **Engine / Kaggle Bundle** panel in this order:

1. **Upload Engine**
   - official competition source ZIP containing `Export.cpp`, `README.md`, and its competition license; or
   - Linux x86-64 ELF `libcg.so`.
   - Source ZIPs are compiled locally with `g++ -std=c++20 -O2 -fPIC -shared` and the extracted source is deleted after the build.
2. **Upload Player**
   - Kaggle `.tar.gz` / `.tgz` with root-level `main.py` and `deck.csv`.
3. **Upload Opponent**
   - a second Bundle with the same contract.
4. **Start Official Match**
   - the bridge calls the uploaded Agents in isolated Python processes;
   - each selected action is passed to `BattleStart / GetBattleData / Select / VisualizeData`;
   - each authoritative state is streamed back through WebSocket.
5. **Run Agent Step** advances one official selection at a time.

The Bundle gate rejects archive traversal, links/devices, missing root files, decks other than exactly 60 integer card IDs, and a bundled `cg/libcg.so` whose SHA-256 differs from the registered official engine.

## Card database and deck builder

Upload these three files together through **Upload 3 Files**:

- `card_id_list.csv`
- `EN_Card_Data.csv`
- `attack_id_mapping.json`

They stay inside the local Bridge artifact directory and are not published. The browser then supports:

- card ID/name/type search;
- card details and move text;
- add/remove quantities;
- four-copy enforcement except Basic Energy;
- 60-card count, ACE SPEC count, and Basic Pokémon checks;
- `deck.csv` export in the competition one-ID-per-line format;
- automatic reflection of an uploaded Player Bundle's deck.

## Replay commands

```bash
cd tools/battle_studio/frontend
npm install --no-audit --no-fund
npm test
npm run build
npm run dev -- --host 0.0.0.0
```

Normalize a recorded CABT snapshot stream:

```bash
python tools/battle_studio/backend/replay_converter.py input.json output.json
```

## Tests

```bash
cd tools/battle_studio/backend
python -m py_compile *.py
pytest -q test_artifact_store.py test_replay_converter.py
```

The CI gate also builds/tests the frontend and blocks any changes to `submission/`, root `deck.csv`, `black_engine/`, or `cg/`. It rejects commits containing the restricted official engine source, `libcg.so`, or uploaded card datasets.

## Truth contract

Each frame is a complete immutable snapshot. Events are presentation only. Card instances are keyed by `playerIndex:serial`; `cardId` is metadata and not a match-instance identity. Hidden cards are never inferred.

## Runtime and license boundary

The official engine and supplied card data are competition-restricted materials. This repository contains only the loader, compiler adapter, validation, and visualization code. Actual engine/card bytes are supplied locally by the competition participant, used only in the local Bridge, and are not redistributed by GitHub Pages or the repository.
