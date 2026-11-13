"""Create an allowlisted source copy and fresh venv; never copy .env/data/credentials.

Includes new source files so unfinished Git staging cannot hide integration gaps.
This is a sanitized source-snapshot rehearsal; hosted CI still needs those files
included in the eventual commit. Existing environments and databases are untouched.
"""
import argparse, os, shutil, subprocess, sys
from datetime import datetime,timezone
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TREES=['agapay-backend/app','agapay-backend/tests','agapay-backend/scripts','agapay-backend/simulator','agapay-backend/deploy',
       'agapay-web/src','agapay-web/test','agapay-web/tests','agapay-web/scripts','agapay-web/public',
       'agapay-mobile/lib','agapay-mobile/test','agapay-mobile/assets','agapay-firmware/src','agapay-firmware/include','agapay-firmware/tests','agapay-firmware/docs','agapay-firmware/tools',
       'agapay-docs/contracts','.github/workflows']
SUFFIXES={'.py','.js','.cjs','.mjs','.ts','.tsx','.dart','.html','.css','.json','.yaml','.yml','.h','.cpp','.md','.png','.svg','.ico','.toml','.txt','.acl'}

def snapshot(destination,*,refresh=False):
    if refresh:
        if destination.name!='Agapay' or not destination.resolve().is_relative_to((REPO/'.ci-check').resolve()) or not destination.is_dir():raise ValueError('Refresh only a known workspace .ci-check source copy')
    else:destination.mkdir(parents=True,exist_ok=False)
    paths=[]
    for tree in TREES:
        root=REPO/tree
        if root.exists():paths.extend(p for p in root.rglob('*') if p.is_file() and p.suffix in SUFFIXES and '__pycache__' not in p.parts)
    for project in ('agapay-backend','agapay-web','agapay-mobile','agapay-firmware'):
        root=REPO/project
        paths.extend(p for p in root.iterdir() if p.is_file() and (p.name in {'Dockerfile','.dockerignore','.gitignore','.env.example','pubspec.yaml','pubspec.lock','platformio.ini'} or p.name.startswith(('requirements','next.config','next-env','tsconfig','postcss.config','package'))))
    paths.append(REPO/'.gitignore')
    count=0
    for source in paths:
        # Never copy machine-local firmware credentials or any application DB.
        if source.suffix=='.h' and 'secret' in source.name and '.example.' not in source.name:continue
        if source.name.startswith('.env') and source.name!='.env.example':continue
        relative=source.relative_to(REPO);target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);count+=1
    return count

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',choices=['core','ml','hybrid'],default='core');parser.add_argument('--snapshot-only',action='store_true');args=parser.parse_args()
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f');root=REPO/'.ci-check'/name/'Agapay'
    print('Clean snapshot:',root,flush=True);print('Copied source files:',snapshot(root),flush=True)
    if args.snapshot_only:return
    backend=root/'agapay-backend';environment=backend/'.ci-venv'
    env={key:value for key,value in os.environ.items() if not key.startswith('AGAPAY_') and key not in {'PYTHONPATH','PYTHONHOME'}}
    subprocess.run([sys.executable,'-m','venv',str(environment)],check=True,env=env)
    python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','-c','requirements-lock.txt','-r',f'requirements-ci-{args.profile}.txt'],cwd=backend,check=True,env=env)
    subprocess.run([str(python),'scripts/run_test_profile.py',args.profile],cwd=backend,check=True,env=env)
    subprocess.run([str(python),'-m','app.export_prediction_contracts','--check'],cwd=backend,check=True,env=env)
    print('PASS: fresh environment/profile and contract drift check; no ignored local data or credentials copied.',flush=True)

if __name__=='__main__':main()
