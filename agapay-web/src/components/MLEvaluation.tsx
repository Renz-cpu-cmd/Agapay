"use client";
import {useAlertResource} from "@/hooks/useAlertResource";
import ForecastRegistry,{type Catalog} from "./ForecastRegistry";
import MLWorkspaceHeader from "./MLWorkspaceHeader";

export default function MLEvaluation(){
  const registry=useAlertResource<Catalog>("forecast-registry");
  const artifact=registry.error?null:registry.data?.experimental;
  const scores=artifact?.evaluation?.test;
  const rf=scores?.random_forest,baseline=scores?.persistence;
  const value=(n:number|null|undefined)=>n==null?"—":n.toFixed(2);
  const metrics=[
    {label:"RAINFALL MAE",value:value(rf?.overall.mae_mm),unit:"mm",detail:"Random forest · withheld archived samples"},
    {label:"RAINFALL RMSE",value:value(rf?.overall.rmse_mm),unit:"mm",detail:"Rainfall error · not flood accuracy"},
    {label:"PERSISTENCE MAE",value:value(baseline?.overall.mae_mm),unit:"mm",detail:"Baseline on the same evaluation scope"},
    {label:"EVALUATION SAMPLES",value:rf?.overall.count??"—",unit:"",detail:"Configured artifact · test partition"},
  ];
  const one=rf?.by_horizon?.["1h"]?.overall.mae_mm,base=baseline?.by_horizon?.["1h"]?.overall.mae_mm;
  return <div className="ml-workspace ml-evaluation"><MLWorkspaceHeader page="evaluation"/>
    <section className="ml-station-bar design-panel"><div><span className="ml-eyebrow">DEPLOYED ARTIFACT EVALUATION</span><h3>{artifact?.model_version??"Model evaluation unavailable"}</h3></div><span className="ml-status">{registry.loading?"Checking registry":artifact?.status??"Unavailable"}</span></section>
    {registry.error&&<p role="status" className="form-error">Model registry unavailable. No saved score is substituted.</p>}
    <div className="ml-metrics">{metrics.map(m=><section className="ml-metric design-panel" key={m.label}><span className="ml-eyebrow">{m.label}</span><strong>{m.value}<small> {m.unit}</small></strong><p>{m.detail}</p></section>)}</div>
    <div className="ml-evaluation-grid"><section className="ml-card design-panel"><span className="ml-eyebrow">CANDIDATE VS BASELINE</span><h3>Rainfall accuracy by horizon</h3><div className="ml-table-scroll"><table><thead><tr><th>Horizon</th><th>RF MAE (mm)</th><th>RF RMSE (mm)</th><th>Persistence MAE (mm)</th></tr></thead><tbody>{["1h","2h","3h"].map(h=><tr key={h}><td>{h}</td><td>{value(rf?.by_horizon?.[h]?.overall.mae_mm)}</td><td>{value(rf?.by_horizon?.[h]?.overall.rmse_mm)}</td><td>{value(baseline?.by_horizon?.[h]?.overall.mae_mm)}</td></tr>)}</tbody></table></div><p className="ml-muted">{one!=null&&base!=null?(base<one?`First-hour persistence has lower MAE (${value(base)} mm) than the rainfall model (${value(one)} mm).`:`First-hour rainfall MAE: model ${value(one)} mm; persistence ${value(base)} mm.`):"A first-hour comparison is unavailable for the configured artifact."}</p></section>
      <aside className="ml-overview-aside"><section className="ml-card design-panel"><span className="ml-eyebrow">DATA PROVENANCE</span><h3>Configured evaluation source</h3><dl className="ml-key-values"><div><dt>Source</dt><dd>{artifact?.source??"Unavailable"}</dd></div><div><dt>Training cutoff</dt><dd>{artifact?.training_cutoff??"Unknown"}</dd></div><div><dt>Evaluation</dt><dd>Archived rainfall · millimeters</dd></div></dl><p className="ml-muted">{artifact?.notice??artifact?.reason??"No evaluation evidence available."}</p></section><section className="ml-callout"><span className="ml-eyebrow">VALIDATION BOUNDARY</span><h3>Rainfall skill is not flood accuracy</h3><p>Field water-depth validation, uncertainty, missed events and warning lead times require reviewed site observations.</p></section></aside>
    </div>
    <details className="ml-advanced design-panel"><summary><div><span className="ml-eyebrow">REVIEWED PRODUCTS AND EVIDENCE</span><h3>Model cards, uncertainty and deployment reviews</h3></div><span className="ml-disclosure" aria-hidden="true">+</span></summary><ForecastRegistry/></details>
  </div>;
}
