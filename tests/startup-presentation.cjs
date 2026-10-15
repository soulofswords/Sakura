const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let frames=[],revealed=0,rendered=0;
const ctx={document:{documentElement:{classList:{remove(name){assert.equal(name,'sakura-starting');revealed++;}}}},
    requestAnimationFrame(callback){frames.push(callback);}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/js/startup-presentation.js','utf8').replace('export async function','async function')+'\nthis.finish=finishStartupPresentation;',ctx);
(async()=>{
    const promise=ctx.finish({_renderFrame(){rendered++;}});
    assert.equal(rendered,1);assert.equal(revealed,0);
    frames.shift()();await Promise.resolve();assert.equal(revealed,0,'first compositor frame remains covered');
    frames.shift()();await promise;assert.equal(revealed,1);
    await assert.rejects(ctx.finish({_renderFrame(){throw new Error('GPU failed');}}),/GPU failed/);
    assert.equal(revealed,2,'render failure does not leave controls hidden');
    const html=fs.readFileSync('static/index.html','utf8'),app=fs.readFileSync('static/js/app.js','utf8');
    assert.ok(html.indexOf("classList.add('sakura-starting')")<html.indexOf('rel="stylesheet"'));
    assert.ok(html.includes('html.sakura-starting #viewer { visibility: hidden; }'));
    assert.ok(app.indexOf('await finishStartupPresentation(viewer);')>app.indexOf('await loadAppSettings();'));
    assert.ok(app.indexOf('await finishStartupPresentation(viewer);')<app.indexOf('if (isDesktop) await startDesktopListening();'));
    console.log('PASS: first frame rendered before reveal, compositor settling, error recovery and startup order');
})().catch(error=>{console.error(error);process.exitCode=1;});
