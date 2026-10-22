const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function element(){return {add(item){this.children.push(item);},value:'',textContent:'',children:[],dataset:{},classList:{hidden:true,add(){this.hidden=true;},remove(){this.hidden=false;},contains(){return this.hidden;}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(){},querySelector(selector){return selector==='input'?this.children.find(child=>child.type==='range'):null;}};}
const elements=new Map();function byId(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);}
let handler;const store=new Map();const ctx=vm.createContext({Option:class {constructor(text,value){this.text=text;this.value=value;}},document:{getElementById:byId,createElement:element},window:{addEventListener(type,fn){if(type==='keydown')handler=fn;}},localStorage:{getItem:key=>store.get(key),setItem:(key,value)=>store.set(key,value)}});
vm.runInContext(fs.readFileSync('static/js/model-visibility.js','utf8').replace(/export /g,'')+'\n'+fs.readFileSync('static/js/auto-expressions.js','utf8').replace(/export /g,'')+'\n'+fs.readFileSync('static/js/custom-expressions.js','utf8').replace(/export /g,'')+'\n'+fs.readFileSync('static/js/expression-editor.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,''),ctx);
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
model='pmx/test.pmx';v.clearManualExpression();v.vtuberTrackingMode=false;v.areAiExpressionsAutomatic=()=>false;handler(event('KeyF',true));assert.equal(v.manualExpression.name,'happyCustom','AI manual expressions work with Reactions off');
v.clearManualExpression();v.areAiExpressionsAutomatic=()=>true;handler(event('KeyF',true));assert.equal(v.manualExpression,null,'AI expression hotkeys are blocked with Reactions on');
editor.refresh();assert.equal(list.children[0].children[3].children[0].disabled,true,'Manual preview is visibly disabled in automatic mode');
assert.equal(ctx.hotkeyFor(event('ShiftLeft')),'');
console.log('PASS: individual expression cards, automatic and custom hotkeys, Live2D preview/strength, model isolation, and AI Reactions/manual ownership');

v.live2d=null;v.allMorphNames.push('Hide_Wings');v.partVisibility=new Map([['Hide_Wings',0]]);v.partVisibilityKey='visibility:test';v.setMorph=()=>{};
editor.refresh();const hide=list.children.find(c=>c.dataset.expression==='Hide_Wings');
assert.equal(hide.children[3].children[0].disabled,false);hide.children[3].children[0].onclick();assert.equal(v.partVisibility.get('Hide_Wings'),1);
hide.children[3].children[3].onclick();assert.equal(v.partVisibility.get('Hide_Wings'),0);
hide.querySelector('input').value='100';hide.querySelector('input').oninput();assert.equal(v.partVisibility.get('Hide_Wings'),1);
byId('close-expression-modal').onclick();handler(event('Digit3',false,true));assert.equal(v.partVisibility.get('Hide_Wings'),0);handler(event('Digit3',false,true));assert.equal(v.partVisibility.get('Hide_Wings'),1);
console.log('PASS: visibility preview, off, strength and hotkeys bypass facial ownership and share persistent state');

assert.equal(hide.children[0].children[0].textContent,'Hide Wings');
const visibilityToggle=hide.children[3].children[4];visibilityToggle.onclick();assert.equal(v.partVisibility.get('Hide_Wings'),0);visibilityToggle.onclick();assert.equal(v.partVisibility.get('Hide_Wings'),1);
const markup=fs.readFileSync('static/index.html','utf8');assert.ok(!markup.includes('data-model-tab="visibility"'));assert.ok(!markup.includes('data-model-panel="visibility"'));
console.log('PASS: clear Hide Wings label, explicit toggle and no duplicate Visibility tab');
