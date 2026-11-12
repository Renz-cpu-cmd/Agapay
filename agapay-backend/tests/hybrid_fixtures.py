"""Tiny synthetic integration bundle; no downloaded data or fitted private estimator."""
import csv, hashlib, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION='synthetic-ci-rain-v1'

def build(root:Path):
    root.mkdir(parents=True,exist_ok=True)
    dataset=root/'rain.csv'
    # Only the integration test's explicit July context and its pre-roll/future.
    with dataset.open('w',newline='',encoding='utf-8') as output:
        writer=csv.writer(output);writer.writerow(['timestamp_utc','rainfall_mm','station_id','dataset_source','rainfall_interval_seconds'])
        for i in range(96):writer.writerow([(datetime(2025,6,29,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(),(i%7)*.1,'SYNTHETIC_CI','synthetic_fixture',3600])
    forest=dict(outputs=3,trees=[dict(left=[-1],right=[-1],feature=[-2],threshold=[-2],value=[[1,1,1]])])
    (root/'forest.json').write_text(json.dumps(forest),encoding='utf-8')
    score=dict(overall=dict(count=3,mae_mm=1,rmse_mm=1),by_horizon={'1h':dict(overall=dict(count=1,mae_mm=1,rmse_mm=1))})
    (root/'evaluation.json').write_text(json.dumps(dict(test=dict(random_forest=score,persistence=score))),encoding='utf-8')
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    metadata=dict(version=VERSION,source='synthetic_fixture',license='CC0-1.0 synthetic test fixture only',
        dataset=dict(sha256=sha(dataset)),files={'forest.json':dict(sha256=sha(root/'forest.json'))},
        splits=dict(train=dict(end='2023-12-31T00:00:00Z'),test=dict(count=1)))
    (root/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    return root,dataset
