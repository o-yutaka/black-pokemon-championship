import importlib.util, json
from pathlib import Path
from black_lab import *
ROOT=Path(__file__).resolve().parents[1]

def test_decks_and_handshakes():
    for name in ('mewtwo_spidops','garchomp_spiritomb'):
        d=ROOT/'candidates'/name; m=json.loads((d/'manifest.json').read_text()); deck=read_deck(d/'deck.csv')
        assert validate_deck(deck,set(m['ace_spec_ids']))['ok']
        spec=importlib.util.spec_from_file_location(name,d/'main.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        assert mod.agent(None,None)==deck

def test_selection_contract():
    assert normalize_selection({'select':{'option':[{},{}],'minCount':1,'maxCount':1}},999)==[0]
    assert normalize_selection({'select':{'option':[{},{}],'minCount':0,'maxCount':2}},[])==[]

def test_mewtwo_core():
    assert [erasure_ball_damage(i) for i in range(3)]==[160,220,280]
    assert minimum_erasure_discards(210)==1
    p=MewtwoSpidopsPolicy(); assert p.score_option({'type':T_ATTACK},{'active_id':MEWTWO_EX,'four_rocket':False,'opp_remaining_hp':200,'reservoir_energy':2}) < -1000

def test_garchomp_spiritomb_core():
    assert spiritomb_effective_damage(150,2)==210
    assert garchomp_damage(True,2)==320
    p=GarchompSpiritombPolicy(); c={'active_id':GARCHOMP_EX,'opp_remaining_hp':330,'roserade_count':0}
    assert p.score_option({'type':T_ATTACK,'name':'Corkscrew Dive'},c) > p.score_option({'type':T_ATTACK,'name':'Draconic Buster'},c)
