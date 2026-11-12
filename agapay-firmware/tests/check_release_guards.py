"""Expected compile rejections; uses only the existing synthetic host fixtures."""
from pathlib import Path
import subprocess,sys
runner=Path(__file__).with_name('run_host_tests.py')
for flag,expected in [('--bench-profile','Cardboard bench outputs cannot be enabled'),('--unprovisioned','Release station identity must be provisioned')]:
    result=subprocess.run([sys.executable,str(runner),'--cxx','C:/Python314/python.exe -m ziglang c++','--release-profile',flag],capture_output=True,text=True)
    if result.returncode==0 or expected not in result.stdout+result.stderr:raise SystemExit('Expected release compile rejection missing: '+flag)
    print('PASS: release rejects '+flag)
