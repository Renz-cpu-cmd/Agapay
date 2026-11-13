"""SIMULATED test publisher. Never publish events labeled physical_rain_gauge."""
import argparse
import json
import os
import time
from uuid import uuid4
import paho.mqtt.client as mqtt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station",default="STATION_001")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=1883)
    parser.add_argument("--mm-per-tip",type=float,default=.70)
    parser.add_argument("--tips",type=int,default=5)
    parser.add_argument("--starting-count",type=int,default=0,help="Last accepted SIMULATED lifetime count; needed when repeating a test session")
    parser.add_argument("--spacing",type=float,default=2)
    args=parser.parse_args()
    if args.starting_count<0 or args.tips<0 or args.spacing<=0 or args.mm_per_tip<=0:
        parser.error("Counts must be nonnegative; calibration and spacing must be positive")
    token=os.environ.get("AGAPAY_STATION_INGEST_TOKEN","").strip()
    if not token.startswith("agi_") or len(token)!=47:
        parser.error("Set AGAPAY_STATION_INGEST_TOKEN for this commissioned simulated station")
    if not os.environ.get("AGAPAY_MQTT_USERNAME") or not os.environ.get("AGAPAY_MQTT_PASSWORD"):
        parser.error("A station-scoped broker username/password is required")
    parser_tls=os.environ.get("AGAPAY_MQTT_TLS","").lower()=="true"
    if not parser_tls and args.host not in ("localhost","127.0.0.1","::1"):
        parser.error("Use TLS for MQTT outside loopback development")
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="agapay-SIMULATED-"+uuid4().hex[:8])
    if parser_tls:client.tls_set()
    if os.environ.get("AGAPAY_MQTT_USERNAME"):
        client.username_pw_set(os.environ["AGAPAY_MQTT_USERNAME"],os.environ.get("AGAPAY_MQTT_PASSWORD",""))
    client.connect(args.host,args.port,keepalive=30);client.loop_start()
    started=time.monotonic();boot="SIMULATED_"+uuid4().hex
    try:
        for count in range(args.tips+1):
            uptime=int((time.monotonic()-started)*1000)
            event={"station_id":args.station,"boot_id":boot,"packet_sequence":count+1,"cumulative_tip_count":args.starting_count+count,
                   "boot_start_tip_count":args.starting_count,"interval_start_tip_count":args.starting_count+max(0,count-1),"mm_per_tip":args.mm_per_tip,
                   "rainfall_increment_mm":args.mm_per_tip if count else 0,"device_uptime_ms":uptime,
                   "last_tip_uptime_ms":uptime if count else None,"interval_start_uptime_ms":0,
                   "counter_persisted":True,"data_source":"simulated_rain_gauge","firmware_version":"0.2.0-test"}
            publication=client.publish(f"agapay/exercises/stations/{args.station}/rain",json.dumps({"ingest_token":token,"rain":event}),qos=1,retain=False)
            publication.wait_for_publish(timeout=5)
            print(f"SIMULATED tip_count={count}; no physical hardware observation")
            time.sleep(args.spacing)
    finally:
        client.disconnect();client.loop_stop()


if __name__=="__main__":main()
