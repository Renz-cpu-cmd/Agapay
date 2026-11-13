// Run after next build. Private ephemeral loopback listener; no cookies or form submission.
import {spawn} from 'node:child_process';
import net from 'node:net';
import assert from 'node:assert/strict';
const probe=net.createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const child=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,NODE_ENV:'production'}});
let diagnostics='';child.stdout.on('data',b=>diagnostics+=b);child.stderr.on('data',b=>diagnostics+=b);
try{
 let first;
 for(let i=0;i<120;i++){
  try{first=await fetch(`http://127.0.0.1:${port}/login`,{headers:{'x-nonce':'untrusted-client-value'}});break;}catch{}
  if(child.exitCode!==null)throw Error('Isolated server exited: '+diagnostics);
  await new Promise(resolve=>setTimeout(resolve,250));
 }
 assert.ok(first,'Isolated server did not start');assert.equal(first.status,200);
 const csp=first.headers.get('content-security-policy'),nonce=csp?.match(/'nonce-([^']+)'/)?.[1];assert.ok(nonce&&nonce!=='untrusted-client-value');
 assert.equal(first.headers.get('x-content-type-options'),'nosniff');assert.equal(first.headers.get('x-frame-options'),'DENY');assert.match(first.headers.get('cache-control'),/no-store/);
 const html=await first.text(),scripts=[...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];assert.ok(scripts.length>3);
 for(const [_,attributes]of scripts){assert.ok(attributes.includes(`nonce="${nonce}"`),'An executable SSR script lacks the document nonce');}
 assert.ok(html.includes('localStorage.getItem("agapay-theme")'),'Before-paint theme script missing');
 const second=await fetch(`http://127.0.0.1:${port}/recover`);assert.equal(second.status,200);assert.notEqual(second.headers.get('content-security-policy').match(/'nonce-([^']+)'/)[1],nonce);
 console.log(`PASS: production HTML on isolated port; ${scripts.length} SSR scripts and theme startup carry the document nonce; nonce changes per request; security headers and no-store present.`);
}finally{child.kill();await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));}
