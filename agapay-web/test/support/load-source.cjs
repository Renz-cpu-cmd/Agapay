const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
// Resolve local TypeScript imports in isolated contract tests, just as the app does.
module.exports=function loadSource(file){
  const result={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX},
  }).outputText,{exports:result,require:name=>{
    if(name.startsWith('.')){
      const base=path.resolve(path.dirname(file),name);
      const target=['.ts','.tsx'].map(ext=>base+ext).find(fs.existsSync);
      if(target)return loadSource(target);
    }
    return require(name);
  }});
  return result;
};
