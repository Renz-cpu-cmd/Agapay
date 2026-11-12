const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const {createHash}=require('node:crypto');
function load(file){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,require:name=>name==='./forecast-contract.generated'?load('src/lib/forecast-contract.generated.ts'):require(name)});return exports;}
const {parsePublishedPrediction}=load('src/lib/predictions.ts');
const cases=JSON.parse(fs.readFileSync('../agapay-docs/contracts/published-forecast-cases.json','utf8'));
for(const item of cases)test('OpenAPI shared case: '+item.name,()=>{if(item.valid){const value=parsePublishedPrediction(item.value);assert.equal(value.forecasts[0].water_depth_cm,0);assert.equal(value.forecast_id,item.value.forecast_id);}else assert.throws(()=>parsePublishedPrediction(item.value));});
test('generated TypeScript contract fingerprint matches the checked OpenAPI document',()=>{assert.equal(load('src/lib/forecast-contract.generated.ts').forecastSchemaSha256,createHash('sha256').update(fs.readFileSync('../agapay-docs/contracts/forecasting.openapi.json','utf8').replace(/\r\n/g,'\n')).digest('hex'));});
