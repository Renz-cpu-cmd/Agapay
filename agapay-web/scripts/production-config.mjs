import {isIP} from 'node:net';
export function productionConfig(env){
  if(env.NODE_TLS_REJECT_UNAUTHORIZED==='0')throw Error('Certificate verification cannot be disabled in production');
  if(env.AGAPAY_ENVIRONMENT!=='production')throw Error('Set the production environment explicitly');
  const web=new URL(env.AGAPAY_WEB_ORIGIN||'invalid');
  const api=new URL(env.AGAPAY_API_URL||'invalid');
  const publicOrigin=u=>u.protocol==='https:'&&!u.username&&!u.password&&!u.search&&!u.hash&&['','/'].includes(u.pathname)&&u.hostname.includes('.')&&!isIP(u.hostname)&&!u.hostname.endsWith('.localhost')&&!u.hostname.endsWith('.local');
  if(!publicOrigin(web))throw Error('Production web origin must be reviewed public HTTPS');
  if(!publicOrigin(api)&&!(api.protocol==='http:'&&['127.0.0.1','[::1]','localhost'].includes(api.hostname)&&!api.username&&!api.password&&!api.search&&!api.hash&&['','/'].includes(api.pathname)))throw Error('Backend transport must be verified HTTPS or explicit same-host loopback HTTP');
  return {webOrigin:web.origin,backendOrigin:api.origin};
}
