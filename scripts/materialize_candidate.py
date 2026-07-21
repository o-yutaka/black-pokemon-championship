from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--candidate',choices=['mewtwo_spidops','garchomp_spiritomb'],required=True); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--force',action='store_true'); args=parser.parse_args()
out=args.output.resolve()
if out.exists():
    if not args.force: raise SystemExit(f'output exists: {out}')
    shutil.rmtree(out)
out.mkdir(parents=True)
shutil.copy2(ROOT/'black_lab.py',out/'black_lab.py')
shutil.copy2(ROOT/'candidates'/args.candidate/'deck.csv',out/'deck.csv')
shutil.copy2(ROOT/'candidates'/args.candidate/'manifest.json',out/'manifest.json')
main=f'''from pathlib import Path\nfrom black_lab import build_policy, read_deck\nPOLICY=build_policy("{args.candidate}")\nDECK=read_deck(Path(__file__).with_name("deck.csv"))\nPOLICY.set_deck(DECK)\ndef agent(obs, configuration=None): return POLICY.agent(obs, configuration)\n'''
(out/'main.py').write_text(main)
receipt={'candidate':args.candidate,'status':'MATERIALIZED_STATIC_ONLY','next':'HROS official-engine smoke'}
(out/'materialization_receipt.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt,indent=2))
