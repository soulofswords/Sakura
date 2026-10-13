const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function element(){return {value:'',textContent:'',children:[],dataset:{},classList:{hidden:true,add(){this.hidden=true;},remove(){this.hidden=false;},contains(){return this.hidden;}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(){},querySelector(selector){return selector==='input'?this.children.find(child=>child.type==='range'):null;}};}
const elements=new Map();function byId(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);}
let handler;const store=new Map();const ctx=vm.createContext({document:{getElementById:byId,createElement:element},window:{addEventListener(type,fn){handler=fn;}},localStorage:{getItem:key=>store.get(key),setItem:(key,value)=>store.set(key,value)}});
vm.runInContext(fs.readFileSync('static/js/custom-expressions.js','utf8').replace(/export /g,'')+'\n'+fs.readFileSync('static/js/expression-editor.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,''),ctx);
let model='pmx/test.pmx';const v={vtuberTrackingMode:true,allMorphNames:['笑い','happyCustom'],clearManualExpression(){this.manualExpression=null;},live2d:null};
const editor=ctx.installExpressionEditor(()=>v,()=>model),list=byId('expression-list');editor.refresh();
assert.equal(list.children.length,2,'each detected expression has its own card');
assert.equal(JSON.parse(store.get('sakura_expression_bindings:pmx/test.pmx'))['笑い'].hotkey,'Ctrl+Digit1');
assert.equal(JSON.parse(store.get('sakura_expression_bindings:pmx/test.pmx')).happyCustom.hotkey,'Ctrl+Digit2');
const event=(code,shift=false,ctrl=false)=>({code,shiftKey:shift,ctrlKey:ctrl,target:{closest:()=>false},preventDefault(){},stopImmediatePropagation(){}});
byId('expression-editor-btn').onclick();const second=list.children[1];second.children[3].children[1].onclick();
handler(event('KeyF',true));assert.ok(store.get('sakura_expression_bindings:pmx/test.pmx').includes('Shift+KeyF'));
byId('close-expression-modal').onclick();handler(event('KeyF',true));assert.equal(v.manualExpression.name,'happyCustom');handler(event('KeyF',true));assert.equal(v.manualExpression,null);
model='vrm/other.vrm';handler(event('KeyF',true));assert.equal(v.manualExpression,null,'bindings are isolated per model');
let liveApplied=null;model='live2d/test.model3.json';v.live2d={setExpression(name,weight){liveApplied={name,weight};return true;}};
byId('expression-editor-btn').onclick();assert.equal(list.children.length,2);const first=list.children[0];
const strength=first.querySelector('input');strength.value='65';strength.oninput();first.children[3].children[0].onclick();
assert.deepEqual(liveApplied,{name:'笑い',weight:.65});assert.equal(v.manualExpression.name,'笑い');
strength.value='35';strength.oninput();assert.deepEqual(liveApplied,{name:'笑い',weight:.35});
byId('expression-neutral').onclick();assert.equal(v.manualExpression,null);
byId('close-expression-modal').onclick();handler(event('Digit1',false,true));assert.equal(v.manualExpression.name,'笑い','Live2D expression responds to its automatic Ctrl+1 shortcut');
model='pmx/test.pmx';v.clearManualExpression();v.vtuberTrackingMode=false;handler(event('KeyF',true));assert.equal(v.manualExpression,null,'expression shortcuts are disabled outside VTuber mode');
assert.equal(ctx.hotkeyFor(event('ShiftLeft')),'');
console.log('PASS: individual expression cards, automatic and custom hotkeys, Live2D preview/strength, model isolation, and VTuber-mode restriction');
