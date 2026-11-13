const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const exportsObject={};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/lib/visible-poll.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:exportsObject,AbortController});
const {visiblePoll}=exportsObject;
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function environment(){
  let active=true,wake=()=>{},next=0;const timers=new Map();
  return {timers,active:()=>active,schedule:(fn,delay)=>{const id=++next;timers.set(id,{fn,delay});return id;},cancel:id=>timers.delete(id),
    listen:fn=>{wake=fn;return()=>{wake=()=>{};};},visibility:value=>{active=value;wake();},wake:()=>wake(),
    tick(){const [id,timer]=timers.entries().next().value;timers.delete(id);timer.fn();}};
}
test('hidden and offline reads pause; wake coalesces and aborts the old generation',async()=>{
  const env=environment(),calls=[];let finish;
  const stop=visiblePoll(signal=>{calls.push(signal);return new Promise(resolve=>finish=resolve);},3000,env);
  env.wake();env.wake();assert.equal(calls.length,1);
  env.visibility(false);assert.equal(calls[0].aborted,true);finish();await flush();assert.equal(env.timers.size,0);
  env.visibility(true);assert.equal(calls.length,2);finish();await flush();assert.equal([...env.timers.values()][0].delay,3000);
  stop();assert.equal(env.timers.size,0);assert.equal(calls[1].aborted,true);env.wake();assert.equal(calls.length,2);
});
test('failed reads back off to a bounded 30 seconds and a success resets the interval',async()=>{
  const env=environment();let failed=true,count=0;
  const stop=visiblePoll(async()=>{count++;if(failed)throw Error('synthetic outage');},3000,env);
  await flush();assert.equal([...env.timers.values()][0].delay,6000);
  for(let i=0;i<5;i++){env.tick();await flush();}
  assert.equal([...env.timers.values()][0].delay,30000);
  failed=false;env.tick();await flush();assert.equal([...env.timers.values()][0].delay,3000);assert.equal(count,7);stop();
});
test('many resume events schedule exactly one follow-up while a request is running',async()=>{
  const env=environment();let finish,count=0,wakes=0;
  const stop=visiblePoll(()=>{count++;return new Promise(resolve=>finish=resolve);},3000,env,()=>wakes++);
  env.wake();env.wake();finish();await flush();assert.equal(count,1);assert.equal(env.timers.size,1);assert.equal([...env.timers.values()][0].delay,0);
  env.tick();assert.equal(count,2);assert.equal(wakes,3);stop();finish();await flush();assert.equal(env.timers.size,0);
});
