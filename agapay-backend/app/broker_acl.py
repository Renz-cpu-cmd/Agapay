"""Render a reviewable production ACL; never edit/reload a broker or print secrets."""
import argparse,json,re
from pathlib import Path


def render(records):
    stations=[];seen=set()
    for row in records:
        station=row.get('station_id','')
        if not re.fullmatch(r'[A-Z0-9_-]{3,50}',station) or station in seen:raise ValueError('Invalid/duplicate station identity')
        seen.add(station)
        if row.get('active') is not True:continue
        if row.get('source_class')!='physical_device':raise ValueError('Exercise identities require a separate broker/environment')
        stations.append(station)
    lines=['# Generated from reviewed active physical identities. No anonymous/exercise device access.']
    for station in sorted(stations):
        lines += ['user '+station,'topic write agapay/stations/'+station+'/telemetry','topic write agapay/stations/'+station+'/rain','topic read agapay/stations/'+station+'/rain-ack','topic read agapay/stations/'+station+'/telemetry-ack','topic read agapay/stations/'+station+'/forecast','']
    lines += ['user backend-ingest','topic read agapay/stations/+/telemetry','topic read agapay/stations/+/rain','topic write agapay/stations/+/rain-ack','topic write agapay/stations/+/telemetry-ack','topic write agapay/stations/+/forecast','']
    return '\n'.join(lines)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise SystemExit('Output exists; review differences and choose a new staged path')
    result=render(json.loads(args.input.read_text(encoding='utf-8')))
    with args.output.open('x',encoding='utf-8') as target:target.write(result)
    print('Staged production ACL for review. No broker change was applied.')
