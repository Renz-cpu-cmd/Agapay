"""Offline field-data preparation, reference baselines and transparent JSON adapter.

No collection, training or registration happens on import. Synthetic fixtures
exercise software only and cannot pass the operational approval gate.
"""
import argparse,csv,hashlib,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
from statistics import median
from app.forecast_schemas import ModelCard
from app.prediction_schemas import ModelOutput,PredictionInput

HORIZONS=(30,60,90)
FEATURE_VERSION='minute_median_pairwise_30m_v1'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def stamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Every timestamp must include timezone')
    return result.astimezone(timezone.utc)

def features(history):
    """Same bounded causal feature code in offline evaluation and runtime."""
    from app.services.ml_predictor import assess_input
    if assess_input(history)[0]!='usable':raise ValueError('History fails operational coverage/quality requirements')
    last=history.samples[-1];bins={}
    for sample in history.samples:
        if sample.recorded_at>=last.recorded_at-timedelta(minutes=30):
            bins.setdefault(int(sample.recorded_at.timestamp()//60),[]).append(sample.water_depth_cm)
    points=[(minute,median(values)) for minute,values in sorted(bins.items())]
    if len(points)<3:raise ValueError('Rate coverage is insufficient')
    rate=median((b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(points) for b in points[i+1:])
    return [last.water_depth_cm,rate]

def values(weights,x):
    if len(weights)!=3 or any(len(row)!=3 or any(not math.isfinite(v) for v in row) for row in weights):raise ValueError('Invalid JSON coefficients')
    return [x[0]+row[0]+row[1]*x[0]+row[2]*x[1] for row in weights]

class JsonDepthPredictor:
    def __init__(self,bundle,version):
        if bundle.get('feature_version')!=FEATURE_VERSION:raise ValueError('Unsupported feature pipeline')
        self.bundle=bundle;self.version=version
    def predict(self,history):
        x=features(history)
        if 'decision_validation' in self.bundle:
            from app.ml.decision_evaluation import in_domain
            if not in_domain(x,self.bundle['decision_validation']['feature_domain']):
                from app.services.ml_predictor import PredictionUnavailable
                raise PredictionUnavailable('invalid_data','Input is outside the reviewed training feature domain; forecast withheld.')
        outputs=values(self.bundle['weights'],x)
        # Out-of-range output is unavailable, never silently clipped to look safe.
        return ModelOutput(forecasts=[dict(horizon_minutes=h,water_depth_cm=v) for h,v in zip(HORIZONS,outputs)])

def score(cases,weights):
    result={}
    for name in ('model','persistence','rate'):
        rows=[]
        for case in cases:
            x=case['features'];prediction=values(weights,x) if name=='model' else [x[0]]*3 if name=='persistence' else [x[0]+h*x[1] for h in HORIZONS]
            rows.append([a-b for a,b in zip(prediction,case['targets'])])
        result[name]={str(h):dict(count=len(rows),mae_cm=sum(abs(r[i]) for r in rows)/len(rows),
            rmse_cm=(sum(r[i]**2 for r in rows)/len(rows))**.5,bias_cm=sum(r[i] for r in rows)/len(rows),
            maximum_absolute_error_cm=max(abs(r[i]) for r in rows)) for i,h in enumerate(HORIZONS)}
    return result

def validate_bundle(bundle,*,approval=False):
    if set(bundle)-{'decision_validation'}!={'card','feature_version','weights','train_events','test_cases'}:raise ValueError('Unsupported bundle fields')
    card=ModelCard.model_validate(bundle['card']);cases=bundle['test_cases'];trains=bundle['train_events']
    if bundle['feature_version']!=FEATURE_VERSION or not 1<=len(cases)<=10000 or not 1<=len(trains)<=1000:raise ValueError('Invalid evaluation budgets')
    values(bundle['weights'],[0,0]);train_ids={r['event_id'] for r in trains};test_ids={r['event_id'] for r in cases}
    if len(train_ids)!=len(trains) or train_ids&test_ids:raise ValueError('Events must be withheld as complete disjoint groups')
    for event in trains:
        if stamp(event['target_end'])>card.training_cutoff or stamp(event['start'])>stamp(event['target_end']):raise ValueError('Training labels cross the declared cutoff')
    seen=set()
    for case in cases:
        at=stamp(case['origin']);available=stamp(case['available_at']);key=(case['event_id'],at)
        if key in seen or at<=card.training_cutoff+timedelta(minutes=90):raise ValueError('Duplicate or unpurged held-out origin')
        seen.add(key)
        if not at<=available<=at+timedelta(seconds=120):raise ValueError('Held-out inference input was not available in time')
        if len(case['features'])!=2 or len(case['targets'])!=3 or any(not math.isfinite(v) for v in case['features']+case['targets']):raise ValueError('Invalid held-out case')
        if any(not 0<=v<=1000 for v in [case['features'][0],*case['targets']]):raise ValueError('Wrong target range/units')
        if case['configuration_hash']!=card.configuration_hash:raise ValueError('Calibration boundary cannot be pooled')
    report=score(cases,bundle['weights'])
    decision=None
    if 'decision_validation' in bundle:
        from app.ml.decision_evaluation import evaluate
        decision=evaluate(bundle)
    if approval:
        if card.training_cutoff>datetime.now(timezone.utc):raise ValueError('Training cutoff cannot be in the future')
        if any(stamp(case['origin'])+timedelta(minutes=90)>datetime.now(timezone.utc) for case in cases):raise ValueError('Withheld future targets must already have been observed')
        if card.source_class!='physical_field':raise ValueError('Synthetic data cannot authorize an operational adapter')
        if len(test_ids)<3 or len(train_ids)<3 or len(cases)<30:raise ValueError('At least three real training and withheld events and 30 test origins are required')
        for case in cases:
            if any(not 0<=v<=1000 for v in values(bundle['weights'],case['features'])):raise ValueError('Held-out model outputs exceed supported range')
        if any(report['model'][str(h)]['mae_cm']>=min(report['persistence'][str(h)]['mae_cm'],report['rate'][str(h)]['mae_cm']) for h in HORIZONS):
            raise ValueError('Candidate must beat both agreed reference baselines at every horizon; independent domain review is still required')
        if not decision or not decision['release_ready']:
            raise ValueError('Decision uncertainty/release gate failed: '+('; '.join(decision['reasons']) if decision else 'Separate calibration events and reviewed decision policy required'))
    return card,report

def prepare(csv_path,card):
    """Explicit event split, exact targets, deployment-time feature availability."""
    if csv_path.stat().st_size>100*1024*1024:raise ValueError('Dataset exceeds 100 MiB offline preparation budget')
    raw=csv_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=card.dataset_sha256:raise ValueError('Dataset checksum differs from model card')
    with csv_path.open(newline='',encoding='utf-8-sig') as source:rows=list(csv.DictReader(source))
    if not rows or len(rows)>1000000:raise ValueError('Empty/oversized dataset')
    events={};all_times=set()
    for row in rows:
        at=stamp(row['measured_at']);available=stamp(row['available_at']);depth=float(row['depth_cm']) if row['quality']=='valid' else None
        if row['station_id']!=card.station_id or row['datum']!=card.datum or row['configuration_hash']!=card.configuration_hash or row['source_class']!=card.source_class:
            raise ValueError('Site, datum, calibration and source must agree exactly with the card')
        if row['units']!='cm' or row['quality'] not in ('valid','invalid') or row['partition'] not in ('train','calibration','test') or not row['event_id']:
            raise ValueError('Explicit quality, units and event partition are required')
        if at in all_times or available<at or (row['quality']=='valid' and (not math.isfinite(depth) or not 0<=depth<=1000)):raise ValueError('Duplicate, impossible or nonfinite observation')
        all_times.add(at)
        if row.get('rainfall_mm'):
            amount=float(row['rainfall_mm']);start=stamp(row['rain_interval_start']);end=stamp(row['rain_interval_end']);rain_available=stamp(row['rain_available_at'])
            if not math.isfinite(amount) or amount<0 or not start<end<=rain_available:raise ValueError('Explicit valid rain interval/availability required')
        events.setdefault(row['event_id'],[]).append(dict(row,at=at,available=available,depth=depth))
    examples={'train':[],'calibration':[],'test':[],'unavailable_test':[]};train_events=[];last_end=None
    for identity,group in sorted(events.items(),key=lambda item:min(r['at'] for r in item[1])):
        group.sort(key=lambda r:r['at']);parts={r['partition'] for r in group}
        if len(parts)!=1:raise ValueError('An event cannot appear in multiple partitions')
        if last_end and group[0]['at']<=last_end:raise ValueError('Event intervals overlap; review incident grouping')
        last_end=group[-1]['at'];partition=parts.pop();targets={r['at']:r for r in group if r['quality']=='valid'}
        if partition=='train':
            if max(r['available'] for r in group)>card.training_cutoff:raise ValueError('Training data unavailable at cutoff')
            train_events.append(dict(event_id=identity,start=group[0]['at'].isoformat(),target_end=group[-1]['at'].isoformat()))
        left=0;last_origin=None
        for index,origin in enumerate(group):
            while left<index and group[left]['at']<origin['at']-timedelta(hours=1):left+=1
            # Each supplied event includes one hour of pre-roll, not evaluated origins.
            if origin['at']<group[0]['at']+timedelta(hours=1):continue
            if partition!='train' and origin['at']<=card.training_cutoff+timedelta(minutes=90):continue
            if last_origin and origin['at']-last_origin<timedelta(minutes=5):continue
            if index-left+1>3600:raise ValueError('Observation window exceeds 3600 samples; review cadence/resampling before preparation')
            selected=[r for r in group[left:index+1] if r['available']<=origin['available']]
            future=[targets.get(origin['at']+timedelta(minutes=h)) for h in HORIZONS]
            if not all(future) or not selected or selected[-1]['at']!=origin['at']:continue
            history=PredictionInput(station_id=card.station_id,as_of=origin['available'],timestamp_basis='device_measured',samples=[dict(recorded_at=r['at'],water_depth_cm=r['depth'] if r['quality']=='valid' else None,sensor_quality=r['quality']) for r in selected])
            try:x=features(history)
            except ValueError:
                if partition=='test':
                    examples['unavailable_test'].append(dict(event_id=identity,origin=origin['at'].isoformat(),targets=[r['depth'] for r in future],missingness_regime='input_coverage_or_quality_failed'))
                    last_origin=origin['at']
                continue
            last_origin=origin['at']
            examples[partition].append(dict(event_id=identity,origin=origin['at'].isoformat(),available_at=origin['available'].isoformat(),configuration_hash=card.configuration_hash,
                features=x,targets=[r['depth'] for r in future],storm_intensity=origin.get('storm_intensity') or 'unavailable_not_validated',missingness_regime='complete_usable'))
    if len(examples['train'])<12 or not examples['test']:raise ValueError('Insufficient complete causal train/test examples')
    return examples,train_events

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--csv',required=True,type=Path);parser.add_argument('--card',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--decision-policy',type=Path,help='Reviewed or provisional policy; requires separate calibration partition')
    args=parser.parse_args();card=ModelCard.model_validate_json(args.card.read_text(encoding='utf-8'));examples,events=prepare(args.csv,card)
    import numpy as np
    x=np.array([[1,*r['features']] for r in examples['train']]);y=np.array([[v-r['features'][0] for v in r['targets']] for r in examples['train']])
    # Fixed regularization; no hyperparameter selection on the withheld events.
    weights=np.linalg.solve(x.T@x+np.diag([0,1,1]),x.T@y).T.tolist()
    bundle=dict(card=card.model_dump(mode='json'),feature_version=FEATURE_VERSION,weights=weights,train_events=events,test_cases=examples['test'])
    if args.decision_policy:
        from app.ml.decision_evaluation import DecisionPolicy,evaluate
        policy=DecisionPolicy.model_validate_json(args.decision_policy.read_text(encoding='utf-8'))
        bundle['decision_validation']=dict(policy=policy.model_dump(),feature_domain=[[min(r['features'][i] for r in examples['train']),max(r['features'][i] for r in examples['train'])] for i in range(2)],
            calibration_cases=examples['calibration'],unavailable_test_cases=examples['unavailable_test'])
    _,report=validate_bundle(bundle)
    with args.output.open('x',encoding='utf-8') as output:output.write(json.dumps(bundle,indent=2,allow_nan=False)+'\n')
    from app.ml.decision_evaluation import evaluate
    print(json.dumps(dict(bundle_sha256=digest(bundle),evaluation=report,decision_evaluation=evaluate(bundle),notice='Offline candidate only; not approved or deployed')))

if __name__=='__main__':main()
