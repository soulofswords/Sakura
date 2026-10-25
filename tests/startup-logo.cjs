const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),os=require('os'),{chromium}=require('playwright');
const SHOTS=path.join(os.tmpdir(),'sakura-ui');
const visible=async(page,selector)=>page.locator(selector).evaluate(node=>getComputedStyle(node).display!=='none'&&node.getBoundingClientRect().width>0);
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 fs.mkdirSync(SHOTS,{recursive:true});
 const page=await browser.newPage({viewport:{width:1000,height:720}});
 await page.route('http://startup.test/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('static/index.html','utf8').replace(/<script type="module"[^>]*>[\s\S]*?<\/script>/g,'').replace(/<script type="module"[^>]*><\/script>/g,'')});
    const file='.'+url.pathname;
    if(!fs.existsSync(file))return route.fulfill({status:404,body:''});
    return route.fulfill({contentType:file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/javascript',path:file});});
 for(const [query,expect] of [
    ['?desktop=1&companion=1',{flower:true,title:'Sakura Companion'}],
    ['?library=1&upload=1',{flower:true,title:'Sakura Companion'}],
    ['?desktop=1&companion=1&tracking=1',{flower:false,title:'Sakura Companion'}]]){
    await page.goto('http://startup.test/'+query);
    assert.equal(await visible(page,'#startup-render-status'),true,'The first paint keeps a startup screen until the renderer is ready: '+query);
    assert.equal(await visible(page,'#startup-render-status .startup-logo-flower'),expect.flower,'Flower logo for '+query);
    assert.equal(await visible(page,'#startup-render-status .startup-logo-vtuber'),!expect.flower,'VTuber badge only in tracking startup for '+query);
    const shown=await page.locator('#startup-render-status').evaluate(node=>{const img=[...node.querySelectorAll('img')].find(i=>getComputedStyle(i).display!=='none'&&i.getBoundingClientRect().width>0);return img&&img.getAttribute('src');});
    assert.equal(shown,expect.flower?'/static/assets/desktop-companion.png?v=flower79':'/static/assets/companion-vtuber.png','Companion tracking uses the mode logo, never the standalone VTuber product logo: '+query);
    assert.equal((await page.locator('#startup-render-status strong').textContent()).trim(),expect.title);
    assert.equal(await page.locator('#startup-render-status').evaluate(node=>getComputedStyle(node).backgroundColor),'rgb(9, 7, 19)','Startup screen matches the branded splash background');
    assert.equal(await page.evaluate(()=>document.body.classList.contains('native-renderer')||document.body.classList.contains('desktop-companion')),true);
    await page.screenshot({path:SHOTS+'/startup-'+(query.includes('tracking')?'tracking':query.includes('library')?'library':'companion')+'.png'});
 }
 console.log('PASS: Cloud API, Local LLM and library startups show the flower identity; only ?tracking=1 shows the VTuber badge; palette matches the branded splash.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
