const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const ctx={performance,setTimeout,console,THREE:{Loader:class{}}};vm.runInNewContext(fs.readFileSync('static/js/model-presentation.js','utf8').replace('export async function','async function')+'\nthis.wait=waitForModelGpu;',ctx);
function setup(statuses){const calls=[];const gl={SYNC_GPU_COMMANDS_COMPLETE:1,ALREADY_SIGNALED:2,CONDITION_SATISFIED:3,WAIT_FAILED:4,TIMEOUT_EXPIRED:5,fenceSync(){calls.push('fence');return {};},flush(){calls.push('flush');},clientWaitSync(){calls.push('poll');return statuses.shift()??3;},deleteSync(){calls.push('delete');},isContextLost:()=>false};return {gl,calls,renderer:{getContext:()=>gl}};}
(async()=>{
 const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelViewer','class ModelViewer');
 vm.runInNewContext(source+'\nthis.Viewer=ModelViewer;',ctx);
 let t=setup([5,5,3]);assert.equal(await ctx.wait(t.renderer,()=>true),true);assert.deepEqual(t.calls,['fence','flush','poll','poll','poll','delete']);
 t=setup([4]);assert.equal(await ctx.wait(t.renderer,()=>true),false);assert.equal(t.calls.at(-1),'delete');
 t=setup([5]);assert.equal(await ctx.wait(t.renderer,()=>true,0),false);assert.equal(t.calls.at(-1),'delete');
 t=setup([5,3]);let current=true;setTimeout(()=>current=false,1);assert.equal(await ctx.wait(t.renderer,()=>current),false);assert.equal(t.calls.at(-1),'delete');
 t=setup([]);t.gl.isContextLost=()=>true;assert.equal(await ctx.wait(t.renderer,()=>true),false);assert.equal(t.calls.length,0);
 const viewer=Object.create(ctx.Viewer.prototype);let finishCompile,draws=0;
 t=setup([5,3]);Object.assign(viewer,{model:{},scene:{},camera:{},_displayLoadTicket:1,_displayLoading:false,renderer:{...t.renderer,compileAsync:()=>new Promise(r=>finishCompile=r)},_renderFrame(){draws++;}});
 const old=viewer._finishModelPresentation(1);viewer._displayLoadTicket=2;finishCompile();await old;assert.equal(draws,0);assert.equal(t.calls.length,0,'Stale compile never paints over a newer load');
 viewer.renderer.compileAsync=async()=>{};await viewer._finishModelPresentation(2);assert.equal(draws,1);assert.equal(t.calls.at(-1),'delete');
 console.log('PASS: GPU presentation waits for completed uploads, bounded polling, cancellation/context-loss and sync cleanup');
})().catch(e=>{console.error(e);process.exitCode=1;});
