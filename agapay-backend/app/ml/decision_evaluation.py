"""Event-based evaluation. Provisional policies and synthetic results never approve use.

Intervals use calibration-event maximum residuals (all origins and horizons),
then evaluate coverage on separate later events. Exchangeability is an assumption,
not a guarantee under drift. Bootstrap units are whole events, never adjacent rows.
"""
import math, random, json
from functools import lru_cache
from collections import defaultdict
from datetime import timedelta
from statistics import mean
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    version: str = Field(min_length=3, max_length=100)
    status: Literal['provisional', 'reviewed'] = 'provisional'
    evidence_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    thresholds_cm: list[float] = Field(default=[60, 85, 100], min_length=3, max_length=3)
    nominal_coverage: float = Field(default=.9, ge=.8, le=.99)
    minimum_event_coverage: float = Field(default=.9, ge=.8, le=1)
    maximum_interval_width_cm: float = Field(default=20, gt=0, le=1000)
    measurement_uncertainty_cm: float = Field(default=2, gt=0, le=100)
    maximum_miss_rate: float = Field(default=.1, ge=0, lt=1)
    maximum_false_alarm_ratio: float = Field(default=.2, ge=0, lt=1)
    minimum_lead_minutes: float = Field(default=10, ge=0, le=90)
    minimum_relative_mae_gain: float = Field(default=.05, gt=0, lt=1)
    minimum_test_events: int = Field(default=10, ge=3, le=1000)
    minimum_decision_events: int = Field(default=3, ge=1, le=1000)
    required_storm_intensities:list[str]=Field(default=['extreme'],min_length=1,max_length=20)
    bootstrap_replicates: int = Field(default=200, ge=100, le=1000)
    # Deliberately no invented wet/dry season boundaries.
    months: dict[str, str] = Field(default_factory=lambda: {str(i): f'calendar_month_{i:02}' for i in range(1, 13)})

    @model_validator(mode='after')
    def coherent(self):
        if not 0 < self.thresholds_cm[0] < self.thresholds_cm[1] < self.thresholds_cm[2] <= 1000:
            raise ValueError('Decision thresholds must be ordered in the station datum')
        if set(self.months) != {str(i) for i in range(1, 13)} or any(not v or len(v)>100 for v in self.months.values()):
            raise ValueError('Provide an explicit label for every calendar month')
        if self.status == 'reviewed' and not self.evidence_sha256:
            raise ValueError('Reviewed tradeoffs require external review evidence')
        return self


def distribution(values):
    if not values: return dict(count=0, median=None, p90=None, maximum=None)
    ordered=sorted(values)
    return dict(count=len(values), median=ordered[len(values)//2], p90=ordered[math.ceil(.9*len(values))-1], maximum=ordered[-1])


def in_domain(features, domain):
    return len(features)==2 and all(math.isfinite(v) and bounds[0]<=v<=bounds[1] for v,bounds in zip(features,domain))


def validate_domain(domain):
    if len(domain)!=2 or any(len(row)!=2 or any(not math.isfinite(v) for v in row) or row[0]>=row[1] for row in domain):
        raise ValueError('Training-only feature domain requires two finite ordered ranges')


def evaluate(bundle):
    return _evaluate_cached(json.dumps(bundle,sort_keys=True,separators=(',',':'),allow_nan=False))

@lru_cache(maxsize=8)
def _evaluate_cached(encoded):
    bundle=json.loads(encoded)
    from app.ml.water_depth import values, stamp, HORIZONS, digest
    evidence=bundle.get('decision_validation')
    if evidence is None: return dict(status='unavailable', release_ready=False, reasons=['Separate calibration events and a reviewed decision policy are missing.'])
    if set(evidence)!={'policy','feature_domain','calibration_cases','unavailable_test_cases'}: raise ValueError('Unsupported decision evidence')
    policy=DecisionPolicy.model_validate(evidence['policy']);domain=evidence['feature_domain'];validate_domain(domain)
    calibration=evidence['calibration_cases'];tests=bundle['test_cases'];unavailable=evidence['unavailable_test_cases']
    if not 1<=len(calibration)<=10000 or len(unavailable)>10000: raise ValueError('Decision evaluation budgets exceeded')
    # Reuse causal/range/calibration validation for every calibration origin.
    from app.ml.water_depth import validate_bundle
    validate_bundle({k:v for k,v in dict(bundle,test_cases=calibration).items() if k!='decision_validation'})
    train_ids={r['event_id'] for r in bundle['train_events']};cal_ids={r['event_id'] for r in calibration};test_ids={r['event_id'] for r in tests}
    if train_ids&cal_ids or cal_ids&test_ids: raise ValueError('Training, calibration and test events must be disjoint')
    calibration_end=max(stamp(r['origin'])+timedelta(minutes=90) for r in calibration)
    if min(stamp(r['origin']) for r in tests)<=calibration_end+timedelta(minutes=90): raise ValueError('Purge calibration labels before withheld test origins')
    for cases in (calibration,tests):
        ranges=defaultdict(list)
        for row in cases:ranges[row['event_id']].append(stamp(row['origin']))
        ordered=sorted((min(times),max(times)+timedelta(minutes=90)) for times in ranges.values())
        if any(a[1]>=b[0] for a,b in zip(ordered,ordered[1:])):raise ValueError('Event target windows overlap; independent grouping must be reviewed')
    residuals=defaultdict(list)
    for row in calibration:
        if not in_domain(row['features'],domain): raise ValueError('Calibration features exceed the training-only domain')
        prediction=values(bundle['weights'],row['features'])
        residuals[row['event_id']].append(max(abs(a-b) for a,b in zip(prediction,row['targets'])))
    rank=math.ceil((len(residuals)+1)*policy.nominal_coverage)
    if rank>len(residuals): raise ValueError('Too few independent calibration events for a finite requested interval')
    radius=max(policy.measurement_uncertainty_cm,sorted(max(v) for v in residuals.values())[rank-1])
    enriched=[];seen=set()
    for available,rows in ((True,tests),(False,unavailable)):
        for row in rows:
            at=stamp(row['origin']);key=(row['event_id'],at)
            if key in seen: raise ValueError('Duplicate withheld decision origin')
            seen.add(key)
            if not available:
                if row['event_id'] in train_ids|cal_ids or at<=calibration_end+timedelta(minutes=90): raise ValueError('Unavailable origins violate event separation')
                if len(row['targets'])!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1000 for v in row['targets']): raise ValueError('Unavailable origins still require observed future truth')
            eligible=available and in_domain(row['features'],domain)
            prediction=values(bundle['weights'],row['features']) if eligible else None
            if prediction and any(not 0<=v<=1000 for v in prediction): eligible=False;prediction=None
            enriched.append(dict(row,at=at,eligible=eligible,prediction=prediction))
    def errors(rows):
        result={}
        for i,h in enumerate(HORIZONS):
            active=[r for r in rows if r['eligible']]
            errors=[r['prediction'][i]-r['targets'][i] for r in active]
            result[str(h)]=dict(origins=len(rows),available=len(active),mae_cm=mean(map(abs,errors)) if errors else None,
                rmse_cm=math.sqrt(mean(e*e for e in errors)) if errors else None,
                interval_coverage=mean(abs(e)<=radius for e in errors) if errors else None)
        return result
    groups={}
    for dimension,key in [('site',lambda r:bundle['card']['station_id']),('season',lambda r:policy.months[str(r['at'].month)]),
                          ('intensity',lambda r:str(sum(max(r['targets'])>=v for v in policy.thresholds_cm))),
                          ('storm_intensity',lambda r:r.get('storm_intensity','unavailable_not_validated')),
                          ('missingness',lambda r:r.get('missingness_regime','complete_usable') if r['eligible'] else r.get('missingness_regime','unavailable_or_ood'))]:
        grouped=defaultdict(list)
        for row in enriched:grouped[key(row)].append(row)
        groups[dimension]={label:errors(rows) for label,rows in grouped.items()}
    events=defaultdict(list)
    for row in enriched:events[row['event_id']].append(row)
    event_reports={};event_gains=defaultdict(list);coverage=[]
    for identity,rows in sorted(events.items()):
        active=[r for r in rows if r['eligible']]
        complete=bool(active) and len(active)==len(rows)
        covered=complete and all(abs(a-b)<=radius for r in active for a,b in zip(r['prediction'],r['targets']))
        coverage.append(covered)
        peaks=[]
        for i,h in enumerate(HORIZONS):
            peaks.append(abs(max(r['prediction'][i] for r in active)-max(r['targets'][i] for r in rows)) if active else None)
            if active:
                model=mean(abs(r['prediction'][i]-r['targets'][i]) for r in active)
                for baseline in ('persistence','rate'):
                    base=mean(abs((r['features'][0] if baseline=='persistence' else r['features'][0]+h*r['features'][1])-r['targets'][i]) for r in active)
                    event_gains[f'{baseline}_{h}'].append(base-model)
        event_reports[identity]=dict(errors=errors(rows),all_horizon_event_covered=covered,peak_absolute_error_cm=peaks)
    # Pre-specified deterministic whole-event bootstrap of paired MAE gain.
    bootstrap={};rng=random.Random(36037)
    for key,gains in event_gains.items():
        draws=sorted(mean(rng.choices(gains,k=len(gains))) for _ in range(policy.bootstrap_replicates))
        bootstrap[key]=dict(events=len(gains),mean_gain_cm=mean(gains),lower_95=draws[int(.025*len(draws))],upper_95=draws[min(len(draws)-1,int(.975*len(draws)))])
    decisions={}
    for threshold in policy.thresholds_cm:
        detected=missed=false_alarm=negative=ongoing=0;leads=[]
        for rows in events.values():
            first=min(rows,key=lambda r:r['at'])
            # Events already above threshold at the first observed input cannot
            # establish advance warning. Report them separately, without credit.
            if first.get('features') and first['features'][0]>=threshold:
                ongoing+=1;continue
            truth_times=[r['at']+timedelta(minutes=h) for r in rows for h,v in zip(HORIZONS,r['targets']) if v>=threshold]
            truth_times.extend(r['at'] for r in rows if r.get('features') and r['features'][0]>=threshold)
            # Once already above threshold, an origin cannot earn advance lead time.
            hazard=bool(truth_times); onset=min(truth_times) if hazard else None
            alarm_times=[r['at'] for r in rows if r['eligible'] and max(r['prediction'])>=threshold]
            if hazard:
                lead=max(((onset-at).total_seconds()/60 for at in alarm_times),default=None)
                if lead is not None and lead>=policy.minimum_lead_minutes: detected+=1;leads.append(lead)
                else: missed+=1
            elif alarm_times:false_alarm+=1
            else:negative+=1
        decisions[str(threshold)]=dict(detected_events=detected,missed_events=missed,false_alarm_events=false_alarm,correct_negative_events=negative,already_above_at_start_events=ongoing,
            miss_rate=missed/(detected+missed) if detected+missed else None,false_alarm_ratio=false_alarm/(detected+false_alarm) if detected+false_alarm else None,
            lead_minutes=distribution(leads),onset_basis='first observed withheld target crossing; not continuous physical onset')
    reasons=[]
    if policy.status!='reviewed':reasons.append('Decision tradeoffs are provisional and require independent domain review.')
    if len(events)<policy.minimum_test_events:reasons.append('Insufficient independent withheld events.')
    if mean(coverage)<policy.minimum_event_coverage:reasons.append('Withheld all-horizon event coverage is below policy.')
    if radius*2>policy.maximum_interval_width_cm:reasons.append('Calibrated interval is too wide for intended decisions.')
    if any(not r['eligible'] for r in enriched):reasons.append('Withheld outage/OOD fallback requires explicit review; no forecast is counted as safe.')
    for label in policy.required_storm_intensities:
        if len({r['event_id'] for r in enriched if r.get('storm_intensity')==label})<policy.minimum_decision_events:reasons.append('Required reviewed storm-intensity stratum lacks independent events: '+label)
    if any(v['lower_95']<=0 for v in bootstrap.values()) or len(bootstrap)!=6:reasons.append('Whole-event gain interval does not establish improvement over both baselines.')
    for item in decisions.values():
        if item['detected_events']+item['missed_events']<policy.minimum_decision_events or item['correct_negative_events']+item['false_alarm_events']<policy.minimum_decision_events:reasons.append('Threshold decisions lack positive/negative event coverage.')
        if item['miss_rate'] is None or item['false_alarm_ratio'] is None:reasons.append('Threshold decisions lack positive/alarm evidence.')
        elif item['miss_rate']>policy.maximum_miss_rate or item['false_alarm_ratio']>policy.maximum_false_alarm_ratio:reasons.append('False-alarm/miss/lead-time tradeoff fails policy.')
    from app.ml.water_depth import score
    reference=score(tests,bundle['weights'])
    if any(reference['model'][str(h)]['mae_cm']>(1-policy.minimum_relative_mae_gain)*min(reference[name][str(h)]['mae_cm'] for name in ('rate','persistence')) for h in HORIZONS):reasons.append('Relative baseline gain fails policy.')
    return dict(status='evaluated',release_ready=not reasons,reasons=sorted(set(reasons)),policy=policy.model_dump(),policy_sha256=digest(policy.model_dump()),
        method='calibration_event_max_absolute_residual_all_horizons',nominal_coverage=policy.nominal_coverage,radius_cm=radius,
        calibration_events=len(residuals),test_events=len(events),event_coverage=mean(coverage),by_horizon=errors(enriched),by_event=event_reports,
        groups=groups,paired_event_bootstrap=bootstrap,decisions=decisions,
        intensity_definition='Count of local depth thresholds exceeded by maximum withheld target; separate from reviewed storm intensity',
        peak_error_distribution_by_horizon={str(h):distribution([r['peak_absolute_error_cm'][i] for r in event_reports.values() if r['peak_absolute_error_cm'][i] is not None]) for i,h in enumerate(HORIZONS)},
        notice='Local-depth decision evaluation only. Coverage assumes comparable independent events; no flood accuracy or certification claim.')


def drift_report(rows, domain, *, minimum_observations=30, maximum_ood_fraction=.1):
    """Explicit bounded window supplied by the operator, never automatic retraining."""
    validate_domain(domain)
    if not rows or len(rows)>10000:raise ValueError('Supply 1–10000 timestamped feature observations')
    from app.ml.water_depth import stamp
    times=[stamp(r['measured_at']) for r in rows]
    if any(a>=b for a,b in zip(times,times[1:])):raise ValueError('Drift window must be strictly ordered')
    ood=sum(not in_domain(row['features'],domain) for row in rows)
    return dict(status='insufficient_data' if len(rows)<minimum_observations else 'rollback_required' if ood/len(rows)>maximum_ood_fraction else 'within_feature_domain',
        observations=len(rows),ood_observations=ood,ood_fraction=ood/len(rows),window_start=times[0].isoformat(),window_end=times[-1].isoformat(),
        notice='Feature-domain check only; not residual/concept-drift proof. Disable binding on confirmed regression; never retrain or replay automatically.')


def main():
    import argparse
    from pathlib import Path
    from app.ml.water_depth import validate_bundle
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--drift-input',type=Path)
    args=parser.parse_args()
    if args.bundle.stat().st_size>4*1024*1024:raise ValueError('Bundle exceeds 4 MiB')
    bundle=json.loads(args.bundle.read_text(encoding='utf-8'));validate_bundle(bundle);result=evaluate(bundle)
    if args.drift_input:
        if args.drift_input.stat().st_size>4*1024*1024:raise ValueError('Drift input exceeds 4 MiB')
        result=dict(evaluation=result,drift=drift_report(json.loads(args.drift_input.read_text(encoding='utf-8')),bundle['decision_validation']['feature_domain']))
    with args.output.open('x',encoding='utf-8') as output:output.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('Created decision/drift report; no model, binding, alert or delivery was changed.')

if __name__=='__main__':main()
