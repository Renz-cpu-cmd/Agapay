"""Render an API-reviewed station configuration as an offline firmware header.

No credential, device upload, database mutation or network operation occurs.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'agapay-backend'))
from app.device_config import Installation,configuration_hash


def render(body):
    station=body['station_id']
    import re
    if not re.fullmatch(r'[A-Z0-9_-]{3,50}',station):
        raise ValueError('Invalid station ID')
    installation=Installation.model_validate(body['installation']).model_dump(mode='json')
    digest=configuration_hash(station,body['revision'],installation)
    if digest!=body['config_hash']:
        raise ValueError('Configuration hash mismatch; review the source response')
    names={'installation_height_cm':'SENSOR_HEIGHT_CM','sensor_min_cm':'MIN_DISTANCE_CM','sensor_max_cm':'MAX_DISTANCE_CM',
        'uncertainty_cm':'SENSOR_UNCERTAINTY_CM','range_margin_cm':'RANGE_MARGIN_CM',
        'advisory_cm':'THRESHOLD_ADVISORY_CM','warning_cm':'THRESHOLD_WARNING_CM','critical_cm':'THRESHOLD_EVACUATE_CM','rain_mm_per_tip':'RAIN_MM_PER_TIP'}
    lines=['// Generated from a reviewed API configuration; do not edit individual values.','#pragma once',
        f'constexpr char CONFIGURED_STATION_ID[] = "{station}";',f'constexpr char APPLIED_CONFIG_HASH[] = "{digest}";',
        f'constexpr unsigned INSTALLATION_REVISION = {int(body["revision"])};',
        '// Validation evidence remains in the backend; a hash does not prove physical calibration.']
    lines += [f'constexpr float {name} = {installation[key]:.9g}F;' for key,name in names.items()]
    # C++ requires a decimal/exponent before the F suffix.
    lines=[re.sub(r'= (\d+)F;',r'= \1.0F;',line) for line in lines]
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output exists; preserve/review it before explicitly choosing a new output path')
    args.output.write_text(render(json.loads(args.input.read_text(encoding='utf-8'))),encoding='utf-8')
