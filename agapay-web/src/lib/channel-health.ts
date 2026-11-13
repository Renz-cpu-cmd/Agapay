export type HealthState = "healthy" | "stale" | "invalid" | "no_data" | "unverified" | "disabled" | "unknown" | "disconnected";
export interface HealthChannel {
  state: HealthState; reason: string; observed_at?: string | null; age_seconds?: number | null;
  value?: number | null; unit?: string|null; increment_mm?: number|null; mm_per_tip?: number|null;
  source_trusted?: boolean; ingress_transport?: string; connection_state?: string; connection_observed_at?:string|null; observer_scope?: string;
}
export interface StationChannels {
  water_sensor: HealthChannel; rain_counter: HealthChannel; device_heartbeat: HealthChannel; broker_ingestion: HealthChannel;
  calibration: { state: "documented" | "unconfigured"; reason: string; water_note?: string|null;
    reference_datum?: string|null; rain_configured_mm_per_tip?: number|null; physical_validation: "pending" };
}
export function ageChannels(channels: StationChannels | undefined | null, elapsed: number, heartbeatTtl: number, unavailable: boolean): StationChannels | undefined {
  if (!channels) return undefined;
  const age=(channel:HealthChannel,ttl:number):HealthChannel=>{
    const ageSeconds=channel.age_seconds == null || !Number.isFinite(elapsed) ? null : channel.age_seconds+Math.max(0,Math.floor(elapsed));
    const state=channel.state==="healthy" ? unavailable || ageSeconds===null ? "unknown" : ageSeconds>ttl ? "stale" : "healthy" : channel.state;
    return {...channel,age_seconds:ageSeconds,state,reason:unavailable ? `Monitoring API unavailable; ${channel.reason}` : state!==channel.state ? `Observation expired; ${channel.reason}` : channel.reason};
  };
  return {...channels,water_sensor:age(channels.water_sensor,heartbeatTtl),device_heartbeat:age(channels.device_heartbeat,heartbeatTtl),
    rain_counter:age(channels.rain_counter,30),broker_ingestion:age(channels.broker_ingestion,30)};
}
