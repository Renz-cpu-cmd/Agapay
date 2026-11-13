const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const exportsObject={};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/app/(command)/error.tsx'),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX},
}).outputText,{exports:exportsObject,require});

test('Try again invokes the framework refetch callback and does not misdiagnose every page failure',()=>{
  let calls=0;
  const tree=exportsObject.default({retry:()=>calls++});
  const [message,button]=tree.props.children;
  assert.equal(message.props.role,'alert');
  assert.doesNotMatch(message.props.children,/account service|backend is running/i);
  button.props.onClick();
  assert.equal(calls,1);
});
