const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
// The phone must be able to take over an expression chosen on the PC, even
// while Reactions are on. This drives the real poll loop from mobile-link.js.
const elements={};
for(const id of ['phone-link-enabled','phone-link-status','phone-link-address','phone-link-code','phone-link-copy-address','phone-link-copy-code','phone-link-advanced','tracking-hands-enabled','send-model-mobile','tracking-modal','connect-phone-btn','tracking-connect-phone-btn','settings-connect-phone-btn','phone-link-existing','phone-link-new','tracking-status','settings-camera-status'])elements[id]={value:'',checked:false,disabled:false,textContent:'',hidden:false,classList:{add(){},remove(){},contains(){return true;}},addEventListener(){},setAttribute(){},getAttribute(){return 'false';},scrollIntoView(){},dispatchEvent(){}};
elements['phone-link-devices']=null;
const queue=[],posted=[];
let commands=[];
const viewer={
  allMorphNames:['Angry','Happy'],manualExpressions:new Map([['Angry',1]]),manualExpression:{name:'Angry',weight:1},
  model:null,lastModelUrl:'',morphs:[],cleared:0,
  areAiExpressionsAutomatic(){return true;},
  setMorph(name,value){this.morphs.push([name,value]);},
  clearManualExpression(){this.manualExpressions.clear();this.manualExpression=null;this.cleared++;}
};
const clock={now:0};
const ctx={
  document:{getElementById:id=>id in elements?elements[id]:null,querySelector:()=>null,createElement:()=>({append(){},before(){},addEventListener(){}})},
  window:{SAKURA_EDITION:'companion',addEventListener(){},dispatchEvent(){}},performance:{now:()=>clock.now},
  setTimeout(fn){queue.push(fn);},HeadPoseFilter:class{},Event:class{},
  fetch:async(url,options)=>{
    if(url==='/api/mobile/poll'){
      const state=JSON.parse(options.body);if(Object.keys(state).length)posted.push(state);
      return{ok:true,json:async()=>({enabled:true,commands:commands.splice(0)})};
    }
    if(options)return{ok:true,json:async()=>({enabled:true,addresses:['http://192.168.1.2:8771'],code:'123456'})};
    return{ok:true,json:async()=>({enabled:false})};
  }
};
vm.runInNewContext(fs.readFileSync('static/js/mobile-link.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export function','function')+'\nthis.install=installMobileLink;',ctx);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const runTick=async()=>{const next=queue.shift();assert.ok(next,'poll loop must keep scheduling');next();await settle();await settle();};
(async()=>{
  ctx.install(()=>viewer,()=>null,()=>{},()=>{});
  await settle();
  elements['phone-link-enabled'].checked=true;elements['phone-link-enabled'].onchange();await settle();
  commands=[{type:'expression',name:'Happy',enabled:true}];clock.now=2000;await runTick();
  assert.deepEqual([...viewer.manualExpressions.keys()],['Happy'],'phone pick replaces the expression enabled on the PC');
  assert.equal(viewer.manualExpression.name,'Happy');
  assert.equal(viewer.cleared,1,'the previous PC selection is cleared first');
  assert.deepEqual(viewer.morphs.at(-1),['Happy',1],'PMX/VRM picks are applied immediately');
  clock.now=3600;await runTick();
  assert.deepEqual(posted.at(-1).active_expressions,['Happy'],'the phone is told which expression is active');
  commands=[{type:'expression',name:'Happy',enabled:false}];clock.now=4000;await runTick();
  assert.equal(viewer.manualExpressions.size,0,'the phone can turn the expression off again');
  assert.equal(viewer.manualExpression,null);
  assert.deepEqual(viewer.morphs.at(-1),['Happy',0]);
  clock.now=5400;await runTick();
  assert.deepEqual(posted.at(-1).active_expressions,[],'clearing is reflected back to the phone');

  const line=fs.readFileSync('static/js/app.js','utf8').split('\n').find(row=>row.includes('viewer.areAiExpressionsAutomatic = '));
  const predicate={reactionsEnabled:true,trackingOnly:false,viewer:{vtuberTrackingMode:false,companionTracking:false,manualExpressions:new Map()}};
  const evaluate=()=>vm.runInNewContext(line.trim()+'\nviewer.areAiExpressionsAutomatic();',predicate);
  assert.equal(evaluate(),true,'reactions stay automatic with no manual pick');
  predicate.viewer.manualExpressions.set('Angry',1);
  assert.equal(evaluate(),false,'a held manual expression pauses automatic reactions');
  predicate.viewer.manualExpressions.clear();predicate.viewer.vtuberTrackingMode=true;
  assert.equal(evaluate(),false,'pure VTuber tracking still mutes reactions');
  predicate.viewer.companionTracking=true;
  assert.equal(evaluate(),true,'the companion tracking add-on keeps reactions');
  console.log('PASS: phone expression picks override PC selections, replace each other and pause reactions until cleared');
})().catch(error=>{console.error(error);process.exitCode=1;});
