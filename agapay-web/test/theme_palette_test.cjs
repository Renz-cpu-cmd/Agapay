const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),postcss=require('postcss');
const css=postcss.parse(fs.readFileSync('src/index.css','utf8'));
function palette(selector){const values={};css.walkRules(selector,rule=>rule.walkDecls(/^--/,d=>values[d.prop]=d.value));return values;}
const light=palette(':root:not([data-theme="dark"])'),dark=palette(':root[data-theme="dark"]');
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);}
test('every shared adaptive color used without a fallback exists in both themes',()=>{
 const required=new Set(files('src').filter(f=>/\.(tsx?|css)$/.test(f)).flatMap(f=>[...fs.readFileSync(f,'utf8').matchAll(/var\((--adaptive-[a-z-]+)\)/g)].map(m=>m[1])));
 for(const [theme,values] of [['light',light],['dark',dark]])for(const token of required)assert.ok(values[token],`${theme} is missing ${token}`);
});
function luminance(hex){const rgb=hex.replace('#','').match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
test('selected and muted navigation labels remain readable and distinct in both themes',()=>{
 for(const [theme,p] of [['light',light],['dark',dark]]){
  assert.notEqual(p['--adaptive-muted'],p['--adaptive-blue']);
  assert.notEqual(p['--navigation-hover'],p['--navigation-selected']);
  assert.ok(contrast(p['--adaptive-muted'],p['--adaptive-surface'])>=4.5,`${theme} muted label`);
  assert.ok(contrast(p['--adaptive-blue'],p['--navigation-selected'])>=4.5,`${theme} selected label`);
 }
});
test('themeable icons retain original vector geometry without baked inactive opacity',()=>{
 const directory='public/figma/website/monochrome';
 for(const name of fs.readdirSync(directory)){
  const original=fs.readFileSync(`public/figma/website/${name}`,'utf8'),mask=fs.readFileSync(`${directory}/${name}`,'utf8');
  const geometry=svg=>[...svg.matchAll(/\b(?:d|viewBox|points|cx|cy|r|x1|x2|y1|y2)="[^"]*"/g)].map(m=>m[0]);
  assert.deepEqual(geometry(mask),geometry(original),`${name} silhouette changed`);
  assert.ok(!/\b(?:fill-|stroke-)?opacity=/.test(mask),`${name} has a baked theme state`);
 }
});
