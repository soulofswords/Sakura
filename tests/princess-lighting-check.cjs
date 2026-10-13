const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--enable-webgl','--use-angle=d3d11']});
 const page=await browser.newPage({viewport:{width:460,height:760},deviceScaleFactor:1});
 await page.goto('http://127.0.0.1:8766/static/library-audit.html');
 await page.waitForFunction(()=>window.auditReady);
 const result=await page.evaluate(()=>window.auditModel('pmx/Miku universe/Miku/Miku-Elegant Princess/Miku-Elegant Princess.pmx'));
 fs.mkdirSync('audit-results/princess-lighting',{recursive:true});
 await page.screenshot({path:`audit-results/princess-lighting/${process.env.AUDIT_LABEL||'check'}.png`});
 console.log(JSON.stringify({ok:result.ok,errors:result.errors,visiblePixels:result.visiblePixels}));
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
