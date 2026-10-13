const fs=require('node:fs');const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:650,height:900}});
  await page.goto('http://127.0.0.1:8766/static/library-audit.html');await page.waitForFunction(()=>window.auditReady);
  await page.evaluate(()=>window.auditModel('pmx/Ananta/Taffy/Taffy.pmx'));
  const stats=await page.evaluate(()=>{
   const out=[];window.auditViewer.model.traverse(mesh=>{
    (Array.isArray(mesh.material)?mesh.material:[]).forEach((m,index)=>{
     if(!/^f头发/.test(m.name)) return;
     const canvas=document.createElement('canvas');canvas.width=m.map.image.width;canvas.height=m.map.image.height;
     const ctx=canvas.getContext('2d');ctx.drawImage(m.map.image,0,0);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
     const uv=mesh.geometry.attributes.uv,indices=mesh.geometry.index,g=mesh.geometry.groups.find(g=>g.materialIndex===index);const samples=[];
     for(let i=g.start;i<g.start+g.count;i+=3){let u=0,v=0;for(let j=0;j<3;j++){const n=indices.getX(i+j);u+=uv.getX(n)/3;v+=uv.getY(n)/3;}
      const x=((Math.round(u*canvas.width)%canvas.width)+canvas.width)%canvas.width,y=((Math.round(v*canvas.height)%canvas.height)+canvas.height)%canvas.height;
      samples.push(pixels[(y*canvas.width+x)*4+3]);}
     out.push({name:m.name,opacity:m.opacity,transparent:m.transparent,depthWrite:m.depthWrite,alphaTest:m.alphaTest,min:Math.min(...samples),max:Math.max(...samples),low:samples.filter(a=>a<240).length,total:samples.length});
    });});return out;
  });
  fs.mkdirSync('audit-results/hair',{recursive:true});fs.writeFileSync('audit-results/hair/alpha.json',JSON.stringify(stats,null,2));
  assert.equal(stats.length,3);assert.ok(stats.every(m=>!m.transparent&&m.depthWrite&&m.alphaTest>=.2));
  await page.screenshot({path:'audit-results/hair/fixed.png'});
  await page.evaluate(()=>{window.auditViewer.model.traverse(mesh=>{for(const m of (Array.isArray(mesh.material)?mesh.material:[]))if(/^f头发/.test(m.name)){
    m.transparent=false;m.alphaTest=.2;m.depthWrite=true;m.needsUpdate=true;}});});
  await page.waitForTimeout(500);await page.screenshot({path:'audit-results/hair/opaque.png'});console.log(JSON.stringify(stats));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
