// Tests each model in a private browser; never changes the companion selection.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(process.env.AUDIT_OUTPUT || 'audit-results/full-library-2026-10-09');
fs.mkdirSync(root, {recursive:true});
fs.mkdirSync(path.join(root,'previews'), {recursive:true});
const output = path.join(root,'results.json');
(async () => {
    const catalog = await (await fetch('http://127.0.0.1:8766/api/models')).json();
    const included = process.env.AUDIT_PATHS ? new Set(JSON.parse(fs.readFileSync(process.env.AUDIT_PATHS,'utf8').replace(/^\uFEFF/,''))) : null;
    const models = catalog.models.map((m,index)=>({...m,index})).filter(m=>
        (!process.env.AUDIT_FILTER || m.path.toLowerCase().includes(process.env.AUDIT_FILTER.toLowerCase())) &&
        (!included || included.has(m.path)) &&
        (!process.env.AUDIT_SHARDS || m.index % +process.env.AUDIT_SHARDS === +process.env.AUDIT_SHARD));
    const results = fs.existsSync(output) ? JSON.parse(fs.readFileSync(output,'utf8')).filter(r=>r.auditVersion==='final3') : [];
    const done = new Set(results.map(r => r.path));
    fs.writeFileSync(path.join(root,'catalog.json'),JSON.stringify(catalog,null,2));
    const browser = await chromium.launch({headless:true,
        executablePath: process.env.AUDIT_CHROMIUM || undefined,
        args:['--enable-webgl','--use-angle=d3d11','--disable-background-timer-throttling']});
    let context, page, errors, warnings, responses, used = 0;
    async function freshPage() {
        if(context) await context.close();
        context = await browser.newContext({viewport:{width:320,height:440},deviceScaleFactor:1});
        page = await context.newPage();
        page.on('pageerror',error => errors.push(error.message));
        page.on('console',msg => { if(['error','warning'].includes(msg.type())) warnings.push(msg.text()); });
        page.on('response', response => {if(response.status() >= 400 && !response.url().endsWith('/textures.json')) responses.push({url:response.url(),status:response.status()});});
        errors=[];warnings=[];responses=[];
        await page.goto('http://127.0.0.1:8766/static/library-audit.html');
        await page.waitForFunction(() => window.auditReady,{timeout:30000});
        used=0;
    }
    for(let i=0;i<models.length;i++) {
        const model=models[i]; if(done.has(model.path)) continue;
        let result;
        try {
            if(!page || used >= 8) await freshPage();
            errors=[];warnings=[];responses=[];
            let timeout;
            try {
                result=await Promise.race([
                    page.evaluate(p => window.auditModel(p),model.path),
                    new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('Model load exceeded 90 seconds')),90000);})
                ]);
            } finally { clearTimeout(timeout); }
            used++;
            result.pageErrors=[...errors];result.warnings=[...warnings];result.failedRequests=[...responses];
            result.ok = result.ok && !errors.length && result.visiblePixels > 20 && result.desktopVisiblePixels > 20;
            if(!result.ok && !result.error) result.error = result.visiblePixels <= 20 ? 'Model renders an empty frame' : 'Renderer error';
            // Sensitive folders are rendered privately without captured previews.
            if(result.ok && !/spicy/i.test(model.path)) {
                const filename=String(model.index).padStart(4,'0')+'.png';
                await page.screenshot({path:path.join(root,'previews',filename),timeout:15000});
                result.preview=filename;
                if(result.desktopPreview) {
                    const full=String(model.index).padStart(4,'0')+'-full.jpg';
                    fs.writeFileSync(path.join(root,'previews',full),Buffer.from(result.desktopPreview,'base64'));
                    result.previewFull=full;
                }
            }
            delete result.desktopPreview;
        } catch(error) {
            result={ok:false,error:error.message,pageErrors:[...errors],warnings:[...warnings]};
            used=8;
        }
        results.push({index:model.index,path:model.path,...result});
        fs.writeFileSync(output,JSON.stringify(results,null,2));
        if(results.length%10===0 || !result.ok) console.log(JSON.stringify({checked:results.length,total:models.length,failures:results.filter(r=>!r.ok).length,last:model.path,ok:result.ok,error:result.error}));
    }
    await browser.close();
    console.log(JSON.stringify({finished:true,checked:results.length,failures:results.filter(r=>!r.ok).length,output}));
})().catch(error=>{console.error(error);process.exitCode=1;});
