const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const loadSource=require('./support/load-source.cjs');
const navigation=loadSource(path.resolve('src/lib/navigation.ts'));
function component(name,role='admin'){
 const exports={};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(`src/components/${name}.tsx`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{exports,require:module=>{
  if(module==='next/link')return ({children,...props})=>React.createElement('a',props,children);
  if(module==='@/context/AccountContext')return {useAccount:()=>({user:{role,name:'Synthetic reviewer'}})};
  if(module==='@/lib/navigation')return navigation;
  if(module==='@/lib/figma-assets')return {figmaAssets:{logo:'/synthetic-logo.png'}};
  if(module==='./DesignUI')return {FigmaIcon:()=>null};
  return require(module);
 }});
 return exports.default;
}
for(const current of ['mlConfiguration','mlEvaluation','forecasts'])test(`${current} has one ML sidebar entry and the correct parent selection`,()=>{
 const html=renderToStaticMarkup(React.createElement(component('Sidebar'),{current,onLogout(){},sosCount:0}));
 assert.equal((html.match(/href="\/ml-configuration"/g)||[]).length,1);
 assert.ok(!html.includes('href="/ml-evaluation"'));
 assert.ok(!html.includes('href="/forecasts"'));
 assert.ok(html.includes(current==='mlConfiguration'?'aria-current="page"':'aria-current="location"'));
 assert.ok(!/practice|simulation/i.test(html));
});
for(const page of ['configuration','evaluation','published'])test(`ML ${page} retains one route per subpage`,()=>{
 const html=renderToStaticMarkup(React.createElement(component('MLWorkspaceHeader'),{page}));
 for(const route of ['/ml-configuration','/ml-evaluation','/forecasts'])assert.equal((html.match(new RegExp(`href="${route}"`,'g'))||[]).length,1);
 assert.equal((html.match(/aria-current="page"/g)||[]).length,1);
 assert.ok(!html.includes('href="/dashboard"'));
});
test('the consolidated sidebar preserves privileged user management',()=>{
 const html=renderToStaticMarkup(React.createElement(component('Sidebar','officer'),{current:'mlEvaluation',onLogout(){},sosCount:0}));
 assert.ok(!html.includes('href="/users"'));
 assert.equal(navigation.navigationGroup('stations'),'stations');
});
