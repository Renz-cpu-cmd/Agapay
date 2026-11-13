"""One exhaustive assignment of backend tests to dependency profiles."""
import argparse, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HYBRID={'tests/test_hybrid_dashboard.py','app/ml/tests/test_hybrid.py'}
ML={'tests/test_water_depth_pipeline.py','app/ml/tests/test_collection.py','app/ml/tests/test_preprocess.py'}

def profiles():
    tests={p.relative_to(ROOT).as_posix() for folder in ('tests','app/ml/tests') for p in (ROOT/folder).rglob('test_*.py')}
    if not (HYBRID|ML)<=tests:raise ValueError('Profile lists name missing tests')
    return dict(core=sorted(tests-HYBRID-ML),ml=sorted(ML),hybrid=sorted(HYBRID))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('profile',choices=['core','ml','hybrid']);parser.add_argument('--list',action='store_true');args=parser.parse_args()
    files=profiles()[args.profile]
    if args.list:print('\n'.join(files));return
    raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q',*files],cwd=ROOT))

if __name__=='__main__':main()
