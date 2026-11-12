"""Loopback-only SIMULATED browser harness. No physical telemetry or safety writes."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from pathlib import Path
import time
from uuid import uuid4
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from app.rain_schemas import RainCounterEvent
from app.services.rain_gauge_service import RainGaugeStore


def create_app(bundle: Path,store_path: Path):
    store=RainGaugeStore(store_path);boot='SIMULATED_'+uuid4().hex;started=time.monotonic();count=sequence=0;last_tip=None
    def send(tip=False):
        nonlocal count,sequence,last_tip
        previous=count;count+=int(tip);sequence+=1;uptime=int((time.monotonic()-started)*1000)
        if tip:last_tip=uptime
        event=RainCounterEvent(station_id='STATION_001',boot_id=boot,packet_sequence=sequence,cumulative_tip_count=count,
            boot_start_tip_count=0,interval_start_tip_count=previous,mm_per_tip=.7,rainfall_increment_mm=.7 if tip else 0,
            device_uptime_ms=uptime,last_tip_uptime_ms=last_tip,interval_start_uptime_ms=0,counter_persisted=True,
            data_source='simulated_rain_gauge',firmware_version='0.2.0-test')
        return store.ingest(event,.7)
    async def heartbeat():
        while True:send();await asyncio.sleep(5)
    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(heartbeat())
        yield
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
    app=FastAPI(title='SIMULATED live-rain browser test only',lifespan=lifespan)
    @app.get('/')
    def page():return FileResponse(bundle)
    @app.get('/api/account/monitoring/stations')
    def no_sensor():return {'stations':[],'stale_after_seconds':30,'checked_at':datetime.now(timezone.utc).isoformat()}
    @app.get('/api/account/rain-gauge/STATION_001')
    def snapshot(source: str='simulated_rain_gauge',since_id: int=0,anchor_at: datetime|None=None):
        if source!='simulated_rain_gauge':raise HTTPException(403,'This test harness has SIMULATED events only; no physical feed')
        return store.snapshot('STATION_001',source,since_id=since_id,anchor_at=anchor_at)
    @app.post('/api/test-tip')
    def simulated_tip():return {'label':'SIMULATED — no physical gauge observation',**send(True)}
    return app


def main():
    import uvicorn
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8012)
    args=parser.parse_args()
    store=args.bundle.parent/f'SIMULATED-browser-{uuid4().hex[:8]}.sqlite3'
    uvicorn.run(create_app(args.bundle,store),host='127.0.0.1',port=args.port)


if __name__=='__main__':main()
