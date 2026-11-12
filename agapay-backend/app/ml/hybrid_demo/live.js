/* Live events stay separate from archived ML inputs and existing safety alerts. */
const LiveRainDemo = (() => {
  class Projection {
    constructor(hydrology) { this.H=hydrology;this.anchor=null;this.lastTip=0;this.forecastCache=null; }
    initialize(depth,at,source) {
      if(!Number.isFinite(depth)||depth<0||!Number.isFinite(Date.parse(at)))throw Error('Valid measured/manual initialization required.');
      this.anchor={depth_cm:depth,at,source};
    }
    rainfall(data,snapshot,contextOrigin,contextIndex,nowMs) {
      let key,history,origin,label;
      if(snapshot.ml_ready){
        const hours=snapshot.completed_hours;
        if(hours.length!==24||hours.some(h=>!h.valid||h.interval_seconds!==3600||!Number.isFinite(h.rainfall_mm))||hours.some((h,i)=>i&&Date.parse(h.timestamp_utc)-Date.parse(hours[i-1].timestamp_utc)!==3600000))throw Error('Completed live history failed cadence validation.');
        origin=Date.parse(hours[23].timestamp_utc);
        if(nowMs-origin<0||nowMs-origin>=3600000)throw Error('Completed gauge history is not current.');
        history=hours.map(h=>h.rainfall_mm);key='genuine:'+JSON.stringify(hours);label='ML rainfall forecast: genuine completed-hour gauge history (source transfer unvalidated)';
      }else{
        if(!Number.isInteger(contextIndex)||contextIndex<23||contextIndex>=data.rainfall_mm.length)throw Error('Select an actual archived 24-hour ERA5 context.');
        origin=contextOrigin;history=data.rainfall_mm.slice(contextIndex-23,contextIndex+1);key='historical:'+contextOrigin;
        label='ML rainfall forecast: historical-context demonstration';
      }
      if(this.forecastCache?.key!==key)this.forecastCache={key,hourly:this.H.predict(data.forest,this.H.featureVector(history,origin)),history,origin,label};
      return this.forecastCache;
    }
    update(data,snapshot,basin,contextOrigin,contextIndex,nowMs,expectedSource) {
      if(!this.anchor)throw Error('Initialize a measured/manual depth first.');
      if(snapshot.data_source!==expectedSource||!snapshot.connected||!Number.isFinite(Date.parse(snapshot.last_received_at))||nowMs-Date.parse(snapshot.last_received_at)>30000||nowMs<Date.parse(snapshot.last_received_at))throw Error('Rain-gauge feed is offline/stale or its source does not match.');
      if(!Number.isFinite(snapshot.rainfall_after_anchor_mm)||snapshot.rainfall_after_anchor_mm<0||Date.parse(snapshot.anchor_at)!==Date.parse(this.anchor.at))throw Error('Rain accumulation must be explicitly aligned after the depth initialization.');
      const elapsed=(nowMs-Date.parse(this.anchor.at))/60000;
      if(elapsed<0)throw Error('Depth initialization is in the future.');
      const forcing=this.rainfall(data,snapshot,contextOrigin,contextIndex,nowMs);
      // Recompute once from the fixed initialization, not from last projected depth.
      const adjusted=this.H.balance(this.anchor.depth_cm,snapshot.rainfall_after_anchor_mm,Math.max(elapsed,1e-9),basin);
      const liveOrigin=snapshot.ml_ready?forcing.origin:Math.floor(nowMs/3600000)*3600000;
      const points=this.H.project(adjusted.depth_cm,forcing.hourly,basin,(nowMs-liveOrigin)/60000);
      points.forEach(p=>p.target_at=new Date(nowMs+p.horizon_minutes*60000).toISOString());
      const freshTip=snapshot.latest_tip_event_id>this.lastTip;
      this.lastTip=Math.max(this.lastTip,snapshot.latest_tip_event_id||0);
      return {points,adjusted,forcing,initial_depth_cm:this.anchor.depth_cm,initial_source:this.anchor.source,
              initialization_at:this.anchor.at,observed_rainfall_since_initialization_mm:snapshot.rainfall_after_anchor_mm,
              generated_at:new Date(nowMs).toISOString(),rainfall_origin:new Date(liveOrigin).toISOString(),new_tip:freshTip,
              data_source:snapshot.data_source,advisory_only:true,depth_is_modeled_after_initialization:true};
    }
  }
  return {Projection};
})();
if(typeof module!=='undefined')module.exports=LiveRainDemo;
