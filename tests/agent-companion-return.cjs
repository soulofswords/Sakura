const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const start=source.indexOf('const setAgentMode=async enabled=>{');
const end=source.indexOf('window.sakuraSetAgentMode=setAgentMode;',start);
function classes(...names){const s=new Set(names);return {contains:x=>s.has(x),remove:(...xs)=>xs.forEach(x=>s.delete(x)),add:(...xs)=>xs.forEach(x=>s.add(x)),toggle(x,on){if(on)s.add(x);else s.delete(x);}};}
(async()=>{
 for(const native of [false,true]){
  let libraryCalls=[],nativeCalls=[];
  const body={classList:classes('agent-mode','native-library')},panel={classList:classes('minimized')},bubble={classList:classes()};
  const ctx={Boolean,trackingOnly:false,document:{body,documentElement:{classList:classes()}},agentModeButton:{setAttribute(){}},agentFrame:{src:'/agent?embedded=1'},chatPanel:panel,chatBubbleBtn:bubble,winMinBtn:{},requestAnimationFrame:fn=>fn(),Event:class{},console,window:{applyLibraryMode:async full=>{libraryCalls.push(full);body.classList.toggle('desktop-companion',!full);body.classList.toggle('native-library',full);},dispatchEvent(){},updateMaximizeControl(){},...(native?{pywebview:{api:{set_library_mode:async full=>nativeCalls.push(full)}}}:{})}};
  vm.runInNewContext(source.slice(start,end)+'this.switchMode=setAgentMode;',ctx);
  await ctx.switchMode(false);
  assert.equal(body.classList.contains('agent-mode'),false);
  assert.equal(body.classList.contains('desktop-companion'),false,'full Companion must not use CSS that hides chat');
  assert.equal(body.classList.contains('native-library'),true);
  assert.equal(panel.classList.contains('minimized'),false);
  assert.equal(bubble.classList.contains('hidden'),true);
  assert.equal(ctx.agentFrame.src,'about:blank');
  assert.ok(libraryCalls.every(Boolean));assert.deepEqual(nativeCalls,[],'return must not shrink the native window');
 }
 console.log('PASS: Agent return restores full Companion chat on native and browser surfaces without shrinking window');
})().catch(e=>{console.error(e);process.exitCode=1;});
