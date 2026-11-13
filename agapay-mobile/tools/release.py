"""Protected Android release builder. No publishing, key generation or device installs."""
import argparse,hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'environment','version','build_number','revision','release_id','api_origin','map_mode','map_origin','map_restriction_evidence_sha256'}

def https(value):
    uri=urlsplit(value);host=uri.hostname or ''
    if uri.scheme!='https' or uri.username or uri.password or uri.query or uri.fragment or uri.path not in ('','/') or '.' not in host or ':' in host or host.endswith(('.local','.localhost')) or re.match(r'^\d',host):raise ValueError('Reviewed public HTTPS origin required')

def configuration(value):
    if set(value)!=FIELDS or value['environment'] not in ('staging','production'):raise ValueError('Explicit staging/production release configuration required')
    if not re.fullmatch(r'\d+\.\d+\.\d+',value['version']) or type(value['build_number']) is not int or not 1<=value['build_number']<=2100000000:raise ValueError('Explicit semantic version and unique positive build number required')
    if not re.fullmatch('[a-f0-9]{40}',value['revision']) or not re.fullmatch('[A-Za-z0-9._-]{3,100}',value['release_id']):raise ValueError('Immutable revision/release identity required')
    https(value['api_origin'])
    if value['map_mode'] not in ('list_only','hosted'):raise ValueError('Unknown map profile')
    if value['map_mode']=='hosted':
        https(value['map_origin'])
        if not re.fullmatch('[a-f0-9]{64}',value['map_restriction_evidence_sha256']):raise ValueError('Retained Maps application/API restriction evidence required')
    return value

def inspect_archive(path):
    with zipfile.ZipFile(path) as archive:
        forbidden=[name for name in archive.namelist() if '/flutter_assets/assets/config/' in '/'+name or Path(name).name in ('.env','key.properties') or name.endswith(('.jks','.keystore','.p12','.p8'))]
    if forbidden:raise ValueError('Release includes development/secret assets: '+', '.join(forbidden))

def run(args,**kwargs):return subprocess.run(args,check=True,text=True,**kwargs)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(config,output,flutter,artifact_format):
    value=configuration(config)
    revision=run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True).stdout.strip()
    if revision!=value['revision'] or run(['git','status','--porcelain'],cwd=ROOT,capture_output=True).stdout.strip():raise ValueError('Release source must match the committed clean revision; do not package a dirty checkout')
    required=['AGAPAY_KEYSTORE_PATH','AGAPAY_KEYSTORE_PASSWORD','AGAPAY_KEY_ALIAS','AGAPAY_KEY_PASSWORD','AGAPAY_UPLOAD_SIGNER_SHA256']
    if not all(os.environ.get(key) for key in required):raise ValueError('Protected signing environment is incomplete')
    store=Path(os.environ['AGAPAY_KEYSTORE_PATH'])
    if not store.is_absolute() or not store.is_file():raise ValueError('Signing key must be an existing protected absolute path')
    output.mkdir(parents=True,exist_ok=False)
    defines=dict(AGAPAY_ENV=value['environment'],AGAPAY_REVISION=revision,AGAPAY_RELEASE_ID=value['release_id'],AGAPAY_API_URL=value['api_origin'],AGAPAY_MAP_MODE=value['map_mode'],AGAPAY_MAP_ORIGIN=value['map_origin'],AGAPAY_MAP_RESTRICTION_EVIDENCE_SHA256=value['map_restriction_evidence_sha256'])
    define_file=output/'build-defines.json';define_file.write_text(json.dumps(defines,indent=2)+'\n',encoding='utf-8')
    args=[flutter,'build',artifact_format,'--release','--flavor',value['environment'],'--build-name',value['version'],'--build-number',str(value['build_number']),'--dart-define-from-file',str(define_file),'--obfuscate','--split-debug-info',str(output/'symbols')]
    if artifact_format=='apk':args+=['--target-platform','android-arm64','--analyze-size']
    run(args,cwd=ROOT)
    flavor=value['environment'];artifact=ROOT/('build/app/outputs/flutter-apk/app-'+flavor+'-release.apk' if artifact_format=='apk' else f'build/app/outputs/bundle/{flavor}Release/app-{flavor}-release.aab')
    inspect_archive(artifact)
    expected=os.environ['AGAPAY_UPLOAD_SIGNER_SHA256'].replace(':','').lower()
    if not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('Invalid expected upload signer identity')
    if artifact_format=='apk':
        signer=os.environ.get('AGAPAY_APKSIGNER')
        if not signer:raise ValueError('Set AGAPAY_APKSIGNER to the reviewed Android SDK apksigner executable')
        verification=run([signer,'verify','--print-certs',str(artifact)],capture_output=True).stdout.lower().replace(':','')
        if expected not in verification:raise ValueError('Artifact signer does not match intended upload signer')
    else:
        run(['jarsigner','-verify',str(artifact)],capture_output=True)
        verification=run(['keytool','-printcert','-jarfile',str(artifact)],capture_output=True).stdout.lower().replace(':','')
        if expected not in verification:raise ValueError('Bundle signer does not match intended upload signer')
    dart_symbols=list((output/'symbols').glob('*'))
    if not dart_symbols:raise ValueError('No split Dart symbols were produced')
    mapping=ROOT/f'build/app/outputs/mapping/{flavor}Release/mapping.txt'
    if not mapping.is_file():raise ValueError('R8 mapping missing; do not release without matching symbols')
    shutil.copyfile(mapping,output/'r8-mapping.txt');shutil.copyfile(artifact,output/artifact.name)
    native=ROOT/f'build/app/outputs/native-debug-symbols/{flavor}Release/native-debug-symbols.zip'
    if native.is_file():shutil.copyfile(native,output/native.name)
    files={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in output.rglob('*') if p.is_file()}
    manifest=dict(configuration=value,artifact=artifact.name,artifact_bytes=artifact.stat().st_size,upload_signer_sha256=expected,files=files,
        native_symbol_archive_present=native.is_file(),device_performance='pending physical-device measurement',store_distribution_signer='Verify separately under Play App Signing; upload signer is not necessarily the installed signer')
    (output/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Artifact and matching symbols archived. No store upload or device installation performed.')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--flutter',default='flutter');parser.add_argument('--format',choices=['apk','appbundle'],default='appbundle');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    config=configuration(json.loads(args.config.read_text(encoding='utf-8')))
    if args.check:print('Public release configuration structurally valid; signer, provider restrictions and device acceptance remain separate.');return
    if not args.output:parser.error('--output must name a new protected artifact directory')
    build(config,args.output.resolve(),args.flutter,args.format)

if __name__=='__main__':main()
