export type OperationalState='unknown'|'stale'|'invalid'|'exercise'|'official';
const states={unknown:['?','No valid reading · current measurement unavailable'],stale:['◷','Last known · stale measurement'],invalid:['!','Latest sample invalid · sensor review needed'],exercise:['◇','Synthetic data · test only'],official:['✓','Official advisory · check issuer and expiry']} as const;
export default function OperationalStateLabel({state,detail}:{state:OperationalState;detail?:string}){
 return <span className="operational-state" data-state={state}><span aria-hidden="true">{states[state][0]}</span>{detail??states[state][1]}</span>;
}
