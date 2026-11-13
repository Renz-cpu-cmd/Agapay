"""Export an approved registry candidate with licence evidence; never auto-install it."""
import argparse, hashlib, json
from pathlib import Path
from app.ml.water_depth import digest, validate_bundle

def verify(root,expected_manifest_sha256):
    if not expected_manifest_sha256 or len(expected_manifest_sha256)!=64:raise ValueError('An externally trusted manifest SHA-256 is required')
    manifest_bytes=(root/'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest()!=expected_manifest_sha256:raise ValueError('Manifest integrity mismatch')
    manifest=json.loads(manifest_bytes)
    if set(manifest)!={'schema_version','model_id','bundle_sha256','review_version','review_evidence_sha256','license_evidence_sha256','license','station_id'} or manifest['schema_version']!=1:
        raise ValueError('Unsupported release manifest')
    for key in ('model_id','bundle_sha256','review_evidence_sha256','license_evidence_sha256'):
        if not isinstance(manifest[key],str) or len(manifest[key])!=64 or any(c not in '0123456789abcdef' for c in manifest[key]):raise ValueError('Missing review/licence identity')
    if not isinstance(manifest['review_version'],int) or manifest['review_version']<1:raise ValueError('Approved registry review required')
    path=root/'bundle.json'
    if path.stat().st_size>4*1024*1024:raise ValueError('Bundle exceeds 4 MiB')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['bundle_sha256']:raise ValueError('Bundle integrity mismatch')
    bundle=json.loads(raw);card,_=validate_bundle(bundle,approval=True)
    if digest(bundle)!=manifest['model_id'] or card.station_id!=manifest['station_id'] or card.data_license!=manifest['license']:raise ValueError('Model/site/licence mismatch')
    return manifest

def export(db,model_id,admin_id,license_evidence_sha256,output):
    from app.models import User
    from app.forecast_models import ForecastModel,ForecastApproval
    user=db.get(User,admin_id);model=db.get(ForecastModel,model_id);approval=db.get(ForecastApproval,model_id)
    if not user or not user.is_active or user.role!='admin':raise ValueError('Active registry administrator required')
    if not model or not approval or approval.state!='approved' or not approval.reviewer_id or approval.reviewer_id==model.registered_by:raise ValueError('Independent approved registry review required')
    if len(license_evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in license_evidence_sha256):raise ValueError('Retain and identify explicit redistribution/licence review evidence')
    validate_bundle(model.bundle,approval=True)
    raw=(json.dumps(model.bundle,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    manifest=dict(schema_version=1,model_id=model_id,bundle_sha256=hashlib.sha256(raw).hexdigest(),review_version=approval.version,
        review_evidence_sha256=approval.evidence_sha256,license_evidence_sha256=license_evidence_sha256,license=model.bundle['card']['data_license'],station_id=model.bundle['card']['station_id'])
    output.mkdir(parents=False,exist_ok=False)
    (output/'bundle.json').write_bytes(raw)
    manifest_bytes=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();(output/'manifest.json').write_bytes(manifest_bytes)
    sha=hashlib.sha256(manifest_bytes).hexdigest();verify(output,sha)
    return sha

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',type=Path);parser.add_argument('--expected-manifest-sha256');parser.add_argument('--model-id');parser.add_argument('--admin-id',type=int);parser.add_argument('--license-evidence-sha256');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.verify:
        verify(args.verify,args.expected_manifest_sha256);print('Release integrity and registry/licence evidence references verified; no model activated.');return
    if not all((args.model_id,args.admin_id,args.license_evidence_sha256,args.output)):parser.error('Export requires model, administrator, licence evidence and a new output directory')
    from app.database import engine,SessionLocal
    from app.migrations import require_current
    require_current(engine)
    with SessionLocal() as db:sha=export(db,args.model_id,args.admin_id,args.license_evidence_sha256,args.output)
    print('Retain this manifest SHA-256 in the protected release record: '+sha)

if __name__=='__main__':main()
