const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});
try{const page=await browser.newPage({viewport:{width:900,height:1000}});page.on('pageerror',e=>console.error(e.stack));await page.goto('http://127.0.0.1:8767/audit.html?no-capture');await page.waitForFunction(()=>window.auditReady);
await page.evaluate(async()=>{const v=window.auditViewer;await v.loadModel('/models/pmx/AI_Assistant_PMX_Models/Tsubaki/Tsubaki.pmx');v.setPhysicsMode('off');v.fullModelView=false;v._autoFrame(v.model);v.camera.zoom=1.6;v.camera.updateProjectionMatrix();v._renderFrame();});
fs.mkdirSync('audit-results/tsubaki',{recursive:true});
const materials=await page.evaluate(()=>{const out=[];window.auditViewer.model.traverse(o=>{for(const m of Array.isArray(o.material)?o.material:[])out.push({name:m.name,side:m.side,specular:m.specular?.toArray(),shininess:m.shininess});});return out;});
for(const name of ['ACC','Clothes']){const material=materials.find(m=>m.name===name);assert.equal(material.side,2);assert.equal(material.shininess,50);assert.ok(material.specular.every(v=>v>.3));}
await page.screenshot({path:'audit-results/tsubaki/repaired.png'});
console.log('PASS: repaired PMX loads with two-sided choker/clothing and restored specular highlights');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
