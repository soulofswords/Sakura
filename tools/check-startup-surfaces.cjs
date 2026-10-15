// Runs against the read-only local model-check server; never enables cameras.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:2}),errors=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('Browser:',e.stack);});
  await page.goto('http://127.0.0.1:8767/audit.html?no-capture');
  await page.waitForFunction(()=>window.auditReady);
  const results=await page.evaluate(async()=>{
   const viewer=window.auditViewer,catalog=await(await fetch('/api/models')).json();
   const pmx=catalog.models.find(m=>/Ringo\/Ringo\.pmx$/i.test(m.path))||catalog.models.find(m=>/\.pmx$/i.test(m.path));
   const vrm=catalog.models.find(m=>/\.vrm$/i.test(m.path));
   const live=catalog.live2d_models[0];
   if(!pmx||!vrm||!live)throw Error('PMX, VRM and Live2D samples required');
   const reports=[];
   for(const model of [pmx,live,vrm,live,pmx]){
    await viewer.loadModel('/models/'+model.path.split('/').map(encodeURIComponent).join('/'));
    for(const quality of ['low','high','balanced','high'])viewer.setQuality(quality);
    for(let i=0;i<15;i++)await new Promise(requestAnimationFrame);
    viewer._renderFrame();
    const gl=viewer.live2d?.app.renderer.gl||viewer.renderer.getContext();gl.finish();
    const width=gl.drawingBufferWidth,height=gl.drawingBufferHeight,pixels=new Uint8Array(width*height*4);
    gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
    let visible=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i]>20)visible++;
    reports.push({path:model.path,width,height,visible,lost:gl.isContextLost(),error:gl.getError(),
      unused3D:viewer.live2d?viewer.renderer.domElement.width:null});
   }
   return reports;
  });
  console.log(JSON.stringify(results));
  assert.deepEqual(errors,[]);
  for(const result of results){
   assert.ok(!result.lost&&result.error===0&&result.visible>1000,JSON.stringify(result));
   assert.ok(result.width*result.height<=4_000_000);
   if(result.unused3D!==null)assert.equal(result.unused3D,1);
  }
  fs.mkdirSync('audit-results/startup',{recursive:true});
  fs.writeFileSync('audit-results/startup/surfaces.json',JSON.stringify({results,errors},null,2));
  console.log('PASS: PMX → Live2D → VRM → Live2D → PMX, quality changes, visible frames, bounded buffers and no WebGL errors');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
