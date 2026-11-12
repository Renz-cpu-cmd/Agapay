"""Export/check forecast contracts from the actual OpenAPI response schemas."""
import argparse,json,hashlib
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.main import app
from app.prediction_schemas import PredictionResponse,PublishedPredictionResponse,PredictionInput,ModelOutput,HORIZONS

ROOT=Path(__file__).resolve().parents[2]
def artifacts():
    api=app.openapi();components=api['components']['schemas'];names={'PredictionResponse','PublishedPredictionResponse','ForecastEnvelope','HybridProjectionRequest','HybridProjectionResponse','RainActivityResponse','ModelCard','CatalogResponse'}
    def refs(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='$ref':yield item.rsplit('/',1)[-1]
                else:yield from refs(item)
        elif isinstance(value,list):
            for item in value:yield from refs(item)
    pending=list(names)
    while pending:
        for name in refs(components[pending.pop()]):
            if name not in names:names.add(name);pending.append(name)
    document={'openapi':api['openapi'],'paths':{key:value for key,value in api['paths'].items() if key.startswith(('/api/predictions/','/api/forecasts/','/api/forecast-workspaces/','/api/forecast-deployments/','/api/hybrid-projections/','/api/rain-activity/','/api/forecast-registry'))},'components':{'schemas':{name:components[name] for name in sorted(names)}}}
    # Registry mutation request schemas are referenced by the exported paths too.
    pending=list(refs(document['paths']))
    while pending:
        name=pending.pop()
        if name not in document['components']['schemas']:
            document['components']['schemas'][name]=components[name];pending.extend(refs(components[name]))
    publication=[key for key in components['PublishedPredictionResponse']['required'] if key not in components['PredictionResponse']['required']]
    encoded=json.dumps(document,sort_keys=True,indent=2)+'\n';checksum=hashlib.sha256(encoded.encode()).hexdigest()
    at=datetime(2026,1,1,tzinfo=timezone.utc)
    sample=PublishedPredictionResponse(uncertainty=dict(method='calibration_event_max_absolute_residual_all_horizons',nominal_coverage=.9,withheld_event_coverage=.9,calibration_events=10,test_events=10,policy_sha256='d'*64,display_resolution_cm=2),station_id='CONTRACT_FIXTURE',reason='Synthetic contract fixture only',checked_at=at,generated_at=at,valid_until=at+timedelta(seconds=60),model_version='b'*64,input_status='usable',input_window_start=at-timedelta(minutes=55),input_last_recorded_at=at,sample_count=12,valid_sample_count=12,timestamp_basis='device_measured',preview_allowed=False,forecasts=[{'horizon_minutes':h,'water_depth_cm':0,'lower_depth_cm':0,'upper_depth_cm':2,'target_at':at+timedelta(minutes=h)} for h in HORIZONS],forecast_id='00000000-0000-4000-8000-000000000001',deployment_version=1,configuration_hash='a'*64,reference_datum='Synthetic contract datum',model_card_id='b'*64,data_cutoff=at,measurement_source='registry_verified_physical_device',ingress_identity='CONTRACT_DEVICE',registry_version=1).model_dump(mode='json')
    cases=[{'name':'published_valid_zero','valid':True,'value':sample}]
    for name,change in [('missing_interval',None),('reversed_interval',3)]:
        changed=deepcopy(sample);changed['forecasts'][0]['lower_depth_cm']=change;cases.append({'name':name,'valid':False,'value':changed})
    for key in publication:
        changed=deepcopy(sample);changed.pop(key);cases.append({'name':'missing_'+key,'valid':False,'value':changed})
    for key,value in [('configuration_hash','wrong'),('measurement_source','simulator'),('data_cutoff','2025-12-31T23:00:00Z'),('model_card_id','c'*64),('generated_at','2026-01-01T00:01:00Z'),('checked_at','2026-01-01T00:00:00')]:
        changed=deepcopy(sample);changed[key]=value;cases.append({'name':'bad_'+key,'valid':False,'value':changed})
    paths={ROOT/'agapay-docs/contracts/forecasting.openapi.json':encoded,ROOT/'agapay-docs/contracts/published-forecast-cases.json':json.dumps(cases,indent=2)+'\n',
        ROOT/'agapay-web/src/lib/forecast-contract.generated.ts':'// Generated from OpenAPI; do not edit.\nexport const forecastSchemaSha256='+json.dumps(checksum)+';\nexport const publishedForecastFields='+json.dumps(publication)+' as const;\n',
        ROOT/'agapay-mobile/lib/models/forecast_contract.generated.dart':"// Generated from OpenAPI; do not edit.\nconst forecastSchemaSha256 = '"+checksum+"';\nconst publishedForecastFields = <String>["+','.join(repr(v) for v in publication)+"];\n"}
    for name,model in [('prediction-input',PredictionInput),('prediction-model-output',ModelOutput),('prediction-response',PredictionResponse)]:
        paths[ROOT/'agapay-docs/contracts'/f'{name}.schema.json']=json.dumps(model.model_json_schema(),indent=2)+'\n'
    return paths

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for path,content in artifacts().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=content:raise SystemExit('Contract drift: '+str(path))
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.is_file() and path.read_text(encoding='utf-8')==content:continue
            temporary=path.with_name(path.name+'.tmp')
            temporary.write_text(content,encoding='utf-8',newline='\n');temporary.replace(path)
    print('Forecast contracts match OpenAPI' if args.check else 'Forecast contracts and synthetic cross-client cases exported')
if __name__=='__main__':main()
