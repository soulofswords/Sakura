const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/js/app.js','utf8'),block=source.slice(source.indexOf('async function enableAiVtuberScreen()'),source.indexOf('async function pollVtuberChat()'));
const checkbox={checked:false},button={setAttribute(name,value){this[name]=value;}};
let toggles=0,stops=0;
const ctx={trackingOnly:false,vtuberEnabled:false,vtuberStartedScreen:false,vtuberPriorReactions:false,reactionsEnabled:false,gameActive:false,lastReactionText:'old',screenReactBtn:button,document:{getElementById(){return checkbox;}},screenShare:{enabled:false,async toggle(){toggles++;this.enabled=true;},stop(){stops++;this.enabled=false;}}};
vm.createContext(ctx);vm.runInContext(block,ctx);
(async()=>{await ctx.enableAiVtuberScreen();assert.equal(toggles,1);assert.equal(ctx.screenShare.enabled,true);assert.equal(ctx.reactionsEnabled,true);assert.equal(checkbox.checked,true);assert.equal(ctx.lastReactionText,'');ctx.restoreAiVtuberScreen();assert.equal(stops,1);assert.equal(ctx.reactionsEnabled,false);
ctx.screenShare.enabled=true;ctx.reactionsEnabled=true;await ctx.enableAiVtuberScreen();ctx.restoreAiVtuberScreen();assert.equal(stops,1,'Previously shared screen remains enabled');assert.equal(ctx.reactionsEnabled,true);
ctx.screenShare.enabled=false;ctx.screenShare.toggle=async()=>{};await assert.rejects(ctx.enableAiVtuberScreen(),/not enabled/);ctx.restoreAiVtuberScreen();ctx.trackingOnly=true;await assert.rejects(ctx.enableAiVtuberScreen(),/Gemini and Local LLM/);console.log('PASS: AI VTuber auto screen/reactions, stopping owned capture, preserving existing sharing, cancellation and tracking-only guard');})().catch(e=>{console.error(e);process.exitCode=1;});
