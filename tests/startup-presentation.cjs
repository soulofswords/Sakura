const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let frames=[],timers=[],revealed=0,rendered=0,ready=0,finished=0;
const ctx={document:{documentElement:{classList:{remove(name){assert.equal(name,'sakura-starting');revealed++;}}}},
    fetch:async(url,options)=>{assert.equal(url,'/api/renderer/ready');assert.equal(options.method,'POST');assert.ok(revealed>0);ready++;return {ok:true};},
    setTimeout(callback){timers.push(callback);},
    requestAnimationFrame(callback){frames.push(callback);}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/js/startup-presentation.js','utf8').replace('export async function','async function')+'\nthis.finish=finishStartupPresentation;',ctx);
(async()=>{
    const promise=ctx.finish({_renderFrame(){rendered++;},renderer:{getContext:()=>({finish(){finished++;}})}});
    assert.equal(rendered,1);assert.equal(revealed,0);
    frames.shift()();await Promise.resolve();assert.equal(revealed,0,'first compositor frame remains covered');
    frames.shift()();await promise;assert.equal(revealed,1);
    assert.equal(ready,1);assert.equal(finished,1,'GPU work completes before reveal and warmup signal');
    await assert.rejects(ctx.finish({_renderFrame(){throw new Error('GPU failed');}}),/GPU failed/);
    assert.equal(revealed,2,'render failure does not leave controls hidden');
    frames=[];timers=[];
    const minimized=ctx.finish(null);
    timers.shift()();await minimized;
    assert.equal(revealed,3,'minimized windows reveal controls without animation frames');
    const html=fs.readFileSync('static/index.html','utf8'),app=fs.readFileSync('static/js/app.js','utf8');
    assert.ok(html.indexOf("classList.add('sakura-starting')")<html.indexOf('rel="stylesheet"'));
    assert.ok(html.includes('html.sakura-starting body > :not(#startup-render-status) { visibility: hidden !important; }'));
    assert.ok(app.indexOf('await finishStartupPresentation(viewer);')>app.indexOf('await loadAppSettings();'));
    assert.ok(app.indexOf('await finishStartupPresentation(viewer);')<app.indexOf('if (isDesktop && !isAgentMode) await startDesktopListening();'));
    console.log('PASS: first frame rendered before reveal, compositor settling, error recovery and startup order');
})().catch(error=>{console.error(error);process.exitCode=1;});
