const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const output=require('./support/load-source.cjs')(path.join(__dirname,'../src/lib/notices.ts'));
const now=Date.parse('2026-10-21T00:00:00Z');
const notice={authority_class:'app_operator',category:'advisory',message_type:'Alert',superseded_by:null,
  effective_at:'2026-10-20T23:00:00Z',expires_at:'2026-10-21T01:00:00Z'};
test('app advisories and official public actions have distinct presentation types',()=>{
  assert.equal(output.noticeKind(notice),'App advisory');
  assert.equal(output.noticeKind({...notice,authority_class:'public_authority'}),'Official advisory');
  assert.equal(output.noticeKind({...notice,authority_class:'public_authority',category:'action'}),'Authority-issued action');
});
test('notice expiry, scheduling, corrections and cancellations re-evaluate without trusting a cached effective label',()=>{
  assert.equal(output.noticeLifecycle(notice,now),'effective');
  assert.equal(output.noticeLifecycle(notice,now+3600000),'expired');
  assert.equal(output.noticeLifecycle(notice,now-7200000),'scheduled');
  assert.equal(output.noticeLifecycle({...notice,superseded_by:'correction'},now),'superseded');
  assert.equal(output.noticeLifecycle({...notice,message_type:'Cancel'},now),'cancelled');
  assert.equal(output.noticeLifecycle({...notice,expires_at:'invalid'},now),'unavailable');
});

const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const fullNotice={...notice,id:'notice-one',authority_id:'AGAPAY_APP_OPS',issuer_name:'AGAPAY App Operations',
  area_ids:['APP'],area_names:['App audience'],status:'Test',urgency:'Expected',severity:'Moderate',certainty:'Possible',
  sent_at:'2026-10-21T00:00:00Z',headline:'Synthetic test advisory',instruction:'Exercise only; follow official local guidance.',reference_id:null};
test('malformed issuers cannot be promoted from sensor data into an official notice',()=>{
  assert.equal(output.parseNoticePage({items:[fullNotice]}).length,1);
  for(const change of [{issuer_name:null},{authority_class:'sensor'},{area_ids:[]},{expires_at:'invalid'},{status:'Actual',category:'action'}])
    assert.throws(()=>output.parseNoticePage({items:[{...fullNotice,...change}]}));
});
function loadComponent(name){
  const result={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,`../src/components/${name}.tsx`),'utf8'),{
    compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
  }).outputText,{exports:result,require:name=>name==='@/lib/notices'?output:name==='@/lib/accounts'?{}:name==='@/lib/alerts'?{alertTime:value=>value}:require(name)});
  return result;
}
test('notice cards visibly retain issuer, area, dates, test status and cancellation references',()=>{
  const Card=loadComponent('OfficialNotices').OfficialNoticeCard;
  const html=renderToStaticMarkup(React.createElement(Card,{notice:{...fullNotice,message_type:'Cancel',reference_id:'original-id'},now}));
  for(const text of ['TEST','App advisory','cancelled','AGAPAY App Operations','AGAPAY_APP_OPS','App audience','2026-10-21T01:00:00Z','References original-id']) assert.ok(html.includes(text),text);
  assert.ok(!html.includes('Authority-issued action'));
});
test('configured sensor threshold guidance never claims mandatory evacuation or community safety',()=>{
  const Thresholds=loadComponent('CommunityAlertThresholds').default;
  const html=renderToStaticMarkup(React.createElement(Thresholds,{station:{id:'SYNTHETIC',thresholds:{advisory:60,warning:85,evacuate:100},dataSource:'device'}}));
  assert.ok(html.includes('not official evacuation orders'));
  assert.ok(!html.includes('Mandatory evacuation'));
  assert.ok(!html.includes('Safe, routine flow'));
  assert.ok(html.includes('local hazards may remain'));
});
