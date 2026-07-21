from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from black_lab import read_deck, validate_deck
reports=[]
for name in ("mewtwo_spidops","garchomp_spiritomb"):
    directory=ROOT/'candidates'/name
    manifest=json.loads((directory/'manifest.json').read_text())
    deck=read_deck(directory/'deck.csv')
    report=validate_deck(deck,set(manifest['ace_spec_ids']))
    if not report['ok']: raise SystemExit(report['violations'])
    spec=importlib.util.spec_from_file_location(f'{name}_main',directory/'main.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    if module.agent(None,None)!=deck: raise SystemExit(f'{name}: handshake mismatch')
    reports.append({**report,'candidate':name,'handshake':'PASS','official_engine':'UNEXECUTED'})
print(json.dumps({'verdict':'STATIC_GATE_PASS_OFFICIAL_ENGINE_HOLD','candidates':reports},indent=2))
