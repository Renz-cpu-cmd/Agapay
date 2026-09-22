"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { tierColor, type AlertTier, type Station } from "@/data/mockData";
import { useMonitoring } from "@/context/MonitoringContext";

const colors = ["#ff0000", "#ff7a00", "#f5df00", "#00e83a"];
const demoRain = [7.1, 5.3, 3.1, 0.3, 4.2, 2.3, 12, 7.2, 1.8, 0.7, 9.3, 5.9];
const chartTick = { fill: "#8292ab", fontSize: 10, fontFamily: "Inter" };
const tooltipStyle = { background: "#00112e", border: "1px solid #6496db", fontSize: 12 };

function tierForDepth(station: Station, depth: number): AlertTier {
  if (depth >= station.thresholds.evacuate) return "EVACUATE";
  if (depth >= station.thresholds.warning) return "WARNING";
  if (depth >= station.thresholds.advisory) return "ADVISORY";
  return "NORMAL";
}

function combinedHistory(stations: Station[]) {
  const count = Math.max(0, ...stations.map(station => station.waterHistory.length));
  return Array.from({ length: count }, (_, index) => {
    const point = stations.map(station => station.waterHistory[index]).find(Boolean);
    return {
      time: point?.time ?? String(index + 1),
      ...Object.fromEntries(stations.map(station => [station.id, station.waterHistory[index]?.level ?? null])),
    };
  });
}

export default function Analytics() {
  const { stations, dataMode } = useMonitoring();
  const [period, setPeriod] = useState("24 Hours");
  const [filter, setFilter] = useState("All Stations");
  const visible = stations.filter(station => filter === "All Stations" || station.id === filter);
  const reportStation = visible[0] ?? stations[0];

  if (!reportStation) {
    return <div className="design-page analytics-screen"><section className="design-panel report-card"><h2>NO MONITORING STATIONS</h2><p className="subtle-note">Register a station to begin collecting telemetry.</p></section></div>;
  }

  const hours: Record<string, number> = { "1 Hour": 1, "6 Hours": 6, "24 Hours": 24, "7 Days": 168 };
  const liveHistory = combinedHistory(visible);
  const history = dataMode === "demo"
    ? Array.from({ length: 24 }, (_, index) => {
        const date = new Date(Date.UTC(2026, 8, 3, 12) - ((23 - index) / 23) * hours[period] * 3_600_000);
        return {
          time: period === "7 Days" ? date.toISOString().slice(5, 16).replace("T", " ") : date.toISOString().slice(11, 16),
          ...Object.fromEntries(visible.map(station => [station.id, station.waterHistory[index]?.level ?? 0])),
        };
      })
    : liveHistory;
  const rainfall = dataMode === "demo"
    ? demoRain.map((value, index) => ({
        time: history[Math.min(history.length - 1, index * 2)]?.time ?? String(index + 1),
        rain: +(value * (filter === "All Stations" ? 1 : reportStation.rainfall / 8.2)).toFixed(1),
      }))
    : (reportStation.rainHistory ?? []).map(point => ({ time: point.time, rain: point.value }));
  const maxWater = Math.max(reportStation.waterLevel, ...reportStation.waterHistory.map(point => point.level));
  const maxTier = tierForDepth(reportStation, maxWater);
  const source = dataMode === "simulator" ? "Virtual station telemetry" : dataMode === "device" ? "Device telemetry" : "Demo series";
  const report = [
    ["Date", reportStation.observedAt ? new Date(reportStation.observedAt).toLocaleString("en-PH") : "Demonstration date"],
    ["Station", reportStation.id],
    ["Max Water Level", `${maxWater.toFixed(1)} cm`],
    ["Max Alert Tier", maxTier],
    ["Period", dataMode === "demo" ? period : `Latest ${history.length} samples`],
    ["Data source", source],
    ["Connection", reportStation.connectionStatus?.replace("_", " ").toUpperCase() ?? (reportStation.isOnline ? "ONLINE" : "OFFLINE")],
    ["Rainfall", `${reportStation.rainfall.toFixed(1)} mm per latest interval`],
    ["Barangay", reportStation.barangay],
  ];

  function download() {
    const rows = [["AGAPAY Flood Event Report", source], ...report];
    const csv = rows.map(row => row.map(value => `"${value.replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `agapay-report-${reportStation.id}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <div className="design-page analytics-screen">
    <div className="design-controls">
      <span className="subtle-note">Period</span>
      <select className="design-input" aria-label="Period" value={period} onChange={event => setPeriod(event.target.value)} disabled={dataMode !== "demo"}>{Object.keys(hours).map(value => <option key={value}>{value}</option>)}</select>
      <select className="design-input" aria-label="Station" value={filter} onChange={event => setFilter(event.target.value)}><option>All Stations</option>{stations.map(station => <option key={station.id}>{station.id}</option>)}</select>
      <span className="subtle-note ml-auto">{source}</span>
    </div>
    <section className="design-panel chart-card">
      <div className="chart-heading"><h2>WATER-LEVEL HISTORY</h2><span className="subtle-note">{dataMode === "demo" ? period.toUpperCase() : `${history.length} RECEIVED SAMPLES`}</span></div>
      <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ top: 4, right: 8, bottom: 6, left: 0 }}><CartesianGrid stroke="#15395e" vertical={false}/><XAxis dataKey="time" tick={chartTick} interval="preserveStartEnd" tickLine={false}/><YAxis tick={chartTick} width={34} tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Legend wrapperStyle={{ fontSize: 10, paddingTop: 15 }}/>{visible.map((station, index) => <Line key={station.id} type="monotone" dataKey={station.id} stroke={colors[index % colors.length]} connectNulls dot={false} strokeWidth={1.5} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div>
    </section>
    <section className="design-panel chart-card">
      <div className="chart-heading"><h2>RAINFALL PER REPORTING INTERVAL (MM)</h2></div>
      <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><BarChart data={rainfall} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}><CartesianGrid stroke="#15395e" vertical={false}/><XAxis dataKey="time" tick={chartTick} tickLine={false}/><YAxis tick={chartTick} width={34} tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="rain" name="Rainfall (mm)" isAnimationActive={false}>{rainfall.map((_, index) => <Cell key={index} fill={index % 6 === 0 ? "#0fa7e6" : "#00516c"}/>)}</Bar></BarChart></ResponsiveContainer></div>
    </section>
    <section className="design-panel report-card"><h2>CURRENT WATER LEVEL - STATION COMPARISON</h2>{visible.map(station => <div className="comparison-row" key={station.id}><header><span style={{ color: tierColor[station.status] }}>● {station.id}</span><span className="text-slate-500">{station.name.replace(" Station", "")}</span><strong style={{ color: tierColor[station.status] }}>{station.waterLevel.toFixed(1)} cm</strong></header><div className="water-bar"><div style={{ width: `${Math.min(100, station.waterLevel / 120 * 100)}%`, background: tierColor[station.status] }}/></div></div>)}</section>
    <section className="design-panel report-card"><h2>FLOOD EVENT REPORT</h2><dl className="report-grid">{report.map(([key, value]) => <div key={key}><dt>{key}</dt><dd style={{ color: key === "Max Alert Tier" ? tierColor[maxTier] : undefined }}>{value}</dd></div>)}</dl><div className="text-center mt-5"><button className="design-button primary small" onClick={download}>DOWNLOAD REPORT</button></div></section>
  </div>;
}
