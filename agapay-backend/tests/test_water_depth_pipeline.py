"""Software-only synthetic fixtures for causal preparation and reference metrics."""
from datetime import timedelta
import csv,hashlib,json,sys
from copy import deepcopy
import pytest
from app.forecast_schemas import ModelCard
from app.ml import water_depth
from test_forecast_registry import candidate

def dataset(tmp_path):
    bundle=candidate(source='synthetic_fixture');card=bundle['card'];cutoff=water_depth.stamp(card['training_cutoff']);rows=[]
    for partition in ('train','test'):
        for event in range(3):
            start=cutoff+timedelta(days=2+event) if partition=='test' else cutoff-timedelta(days=5-event)
            for minute in range(0,241,5):
                at=start+timedelta(minutes=minute)
                rows.append(dict(station_id=card['station_id'],event_id=f'{partition}{event}',partition=partition,measured_at=at.isoformat(),available_at=(at+timedelta(seconds=1)).isoformat(),
                    depth_cm=30+.005*minute+.0001*minute*minute,quality='valid',source_class='synthetic_fixture',datum=card['datum'],units='cm',configuration_hash=card['configuration_hash'],
                    rainfall_mm='',rain_interval_start='',rain_interval_end='',rain_available_at=''))
    path=tmp_path/'synthetic.csv'
    with path.open('w',newline='',encoding='utf-8') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    card['dataset_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return path,card,rows

def rewrite(path,card,rows):
    with path.open('w',newline='',encoding='utf-8') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    card['dataset_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()

def test_offline_training_exact_targets_baselines_and_no_automatic_registration(tmp_path,monkeypatch,capsys):
    path,card,_=dataset(tmp_path);card_path=tmp_path/'card.json';card_path.write_text(json.dumps(card),encoding='utf-8');output=tmp_path/'candidate.json'
    monkeypatch.setattr(sys,'argv',['water_depth','--csv',str(path),'--card',str(card_path),'--output',str(output)])
    water_depth.main();bundle=json.loads(output.read_text());parsed,report=water_depth.validate_bundle(bundle)
    assert parsed.source_class=='synthetic_fixture' and set(report)=={'model','persistence','rate'}
    assert set(row['event_id'] for row in bundle['train_events']).isdisjoint(row['event_id'] for row in bundle['test_cases'])
    assert len(bundle['test_cases'])>=30 and all(report['model'][str(h)]['count']>=30 for h in (30,60,90))
    assert 'not approved or deployed' in capsys.readouterr().out
    with pytest.raises(ValueError,match='Synthetic'):water_depth.validate_bundle(bundle,approval=True)
    with pytest.raises(FileExistsError):water_depth.main()

@pytest.mark.parametrize('change',['wrong_hash','datum','units','late_input','mixed_event','missing_target','invalid_null'])
def test_preparation_preserves_missingness_and_rejects_or_excludes_bad_evidence(tmp_path,change):
    path,card,rows=dataset(tmp_path)
    if change=='wrong_hash':card['dataset_sha256']='0'*64
    if change=='datum':rows[0]['datum']='Different unreviewed gauge zero'
    if change=='units':rows[0]['units']='m'
    if change=='mixed_event':rows[0]['partition']='test'
    if change=='late_input':
        for row in rows:row['available_at']=(water_depth.stamp(row['measured_at'])+timedelta(minutes=10)).isoformat()
    if change=='missing_target':rows=rows[::12]
    if change=='invalid_null':rows[12]['quality']='invalid';rows[12]['depth_cm']=''
    if change!='wrong_hash':rewrite(path,card,rows)
    if change=='invalid_null':
        examples,_=water_depth.prepare(path,ModelCard.model_validate(card))
        invalid=water_depth.stamp(rows[12]['measured_at'])
        assert all(not invalid<=water_depth.stamp(case['origin'])<=invalid+timedelta(hours=1) for case in examples['train'] if case['event_id']=='train0')
    else:
        with pytest.raises(ValueError):water_depth.prepare(path,ModelCard.model_validate(card))
