"use client";
import {LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer} from "recharts";
import {measuredSeries} from "@/lib/staff-workspaces";
import {alertTime} from "@/lib/alerts";
import {measurementText,measurementNote} from "@/lib/measurements";
import {trendLabel,type Station} from "@/data/mockData";

export default function MeasuredTrend({station,maximumGapSeconds}:{station:Station;maximumGapSeconds:number}) {
  const data=measuredSeries(station.waterHistory,maximumGapSeconds);
  const untimed=station.waterHistory.filter(row=>!row.measuredAt||!Number.isFinite(Date.parse(row.measuredAt)));
  const time=(at:number)=>new Date(at).toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Asia/Manila"});
  return <div className="measured-trend"><p><strong>{measurementText(station.depth,1,"cm")}</strong> · {measurementNote(station.depth)} · {station.measurementAge??"Age unknown"}</p>
    <p>{trendLabel[station.trend]} · {station.riseRate==null?"Rate unavailable":`${station.riseRate.toFixed(1)} cm/min`} · {station.trendReason??"Coverage unconfirmed"}</p>
    <p className="subtle-note">Recent monitoring window, up to 120 samples. PHT measurement timeline; gaps longer than {maximumGapSeconds}s and invalid samples break the line. This is not a full event report. {untimed.length} sample(s) have unknown measured time and are excluded from the plotted timeline.</p>
    {data.length?<div className="measured-trend-chart" aria-hidden="true"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:12,right:18,left:0,bottom:12}}><CartesianGrid stroke="var(--adaptive-border)" vertical={false}/><XAxis type="number" dataKey="at" domain={["dataMin","dataMax"]} tickFormatter={time} minTickGap={40} stroke="var(--adaptive-muted)"/><YAxis width={48} unit=" cm" stroke="var(--adaptive-muted)"/><Tooltip labelFormatter={value=>time(Number(value))} contentStyle={{background:"var(--adaptive-surface)",color:"var(--adaptive-text)",border:"1px solid var(--adaptive-border)"}}/><Line dataKey="level" name="Depth (cm)" type="linear" connectNulls={false} stroke="var(--adaptive-blue)" dot={{r:2}} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>:<p>No timestamped observations available.</p>}
    <details><summary>Timestamped measurement data and gaps</summary><div className="design-table-wrap"><table className="design-table"><caption>Same monitoring window as the chart; missing values remain unavailable</caption><thead><tr><th>Measured time (PHT)</th><th>Water depth (cm)</th><th>Quality / gap</th></tr></thead><tbody>{data.map((row,i)=><tr key={`${row.at}-${i}`}><td>{row.gapStart!==undefined?`Gap after ${alertTime(new Date(row.gapStart).toISOString())} until ${alertTime(new Date(row.gapEnd!).toISOString())}`:alertTime(new Date(row.at).toISOString())}</td><td>{row.level??"—"}</td><td>{row.gapStart!==undefined?"No observations in gap":row.level===null?"Missing / invalid observation":"Valid sample"}</td></tr>)}{untimed.map((row,i)=><tr key={`untimed-${i}`}><td>Measured time unknown; received {alertTime(row.receivedAt??null)}</td><td>{row.level??"—"}</td><td>Timing unavailable; not plotted</td></tr>)}</tbody></table></div></details>
  </div>;
}
