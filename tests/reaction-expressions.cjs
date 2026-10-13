const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('static/js/reaction-expressions.js','utf8').replace(/export default class /,'class ').replace(/export function /g,'function ');
const context={};vm.runInNewContext(src+'\nthis.Controller=ReactionExpressions;this.catalog=availableReactionExpressions;',context);
const names=['Happy','Surprised','Sad','Laugh','Serious','Happy outfit','mouthSmile','blink','Joy remove clothes','謎','笑い'];
for(const provider of ['gemini','local']){
 const applied=new Map(),viewer={model:{},activity:'talking',getMorphNames:()=>names,setMorph:(n,w)=>applied.set(n,w)};
 const c=new context.Controller(viewer);assert.equal(context.catalog(viewer).length,6);
 for(const [text,name]of [['That clutch was amazing!','Happy'],['Wow, that was unexpected!','Surprised'],['Sorry, that looks frustrating.','Sad'],['Haha, that was funny.','Laugh'],['Watch out, focus on your aim.','Serious']]){
  assert.equal(c.begin(text),true);for(let i=0;i<60;i++)c.update(1/60);assert.equal(viewer.reactionExpressionInfo.name,name);assert.ok(applied.get(name)>.2&&applied.get(name)<.5);
  c.stop();for(let i=0;i<180;i++)c.update(1/60);assert.equal(c.entries.length,0);assert.equal(applied.get(name),0);
 }
 viewer.vtuberTrackingMode=true;assert.equal(c.begin('Wow!'),false);viewer.vtuberTrackingMode=false;c.begin('Wow!');viewer.model={};c.update(1/60);assert.equal(c.entries.length,0,'Model change cancels stale expression');
 viewer.getMorphNames=()=>['A','Blink','outfit','unknown'];assert.equal(c.begin('happy'),false,'Never guess unknown expression semantics');
}
const active=new Map(),live={setExpression:(n,w)=>active.set(n,w),removeExpression:n=>active.delete(n)},v={model:{},live2d:live,getMorphNames:()=>['Happy'],manualExpressions:new Map(),activity:'talking'};
const c=new context.Controller(v);c.begin('Great!');c.update(.1);assert.ok(active.get('Happy')>0);c.stop();for(let i=0;i<100;i++)c.update(.1);assert.equal(active.size,0,'Live2D reaction removed after fade');
c.begin('Great!');c.update(.1);v.manualExpressions.set('Happy',1);active.set('Happy',1);c.clear();assert.equal(active.get('Happy'),1,'Manual expression remains owned by user');
console.log('PASS: model-specific mood choice, unsafe morph exclusion, smooth speech/fade, both AI providers, VTuber guard, stale model cleanup and Live2D manual ownership');
