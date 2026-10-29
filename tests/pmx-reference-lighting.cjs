const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:700,height:850}}),shaderErrors=[];
  page.on('console',message=>{if(message.type()==='error'&&/Shader Error|VALIDATE_STATUS|shader error/i.test(message.text()))shaderErrors.push(message.text());});
  await page.route('http://pmx.test/**',route=>{
   const url=new URL(route.request().url()),relative=decodeURIComponent(url.pathname).slice(1),file=path.resolve(relative);
   if(!file.startsWith(process.cwd()+path.sep)||!['static','models'].includes(relative.split('/')[0]))return route.fulfill({status:404,body:''});
   if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream',body:fs.readFileSync(file)});
   if(relative.startsWith('models/')&&/\.(png|bmp|tga|dds|sph|spa)$/i.test(relative)){
    const color=url.searchParams.get('fallback')==='black'?'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAX+XDSwAAAABJRU5ErkJggg==':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==';
    return route.fulfill({contentType:'image/png',body:Buffer.from(color,'base64')});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://pmx.test/static/library-audit.html?no-capture');await page.waitForFunction(()=>window.auditReady);
  const result=await page.evaluate(async()=>{
   const loaded=await auditModel('pmx/Miku universe/luka/TDA Traditional Luka/Luka.pmx');
   const m=auditViewer.model.material[8];
   const before=m.uniforms.sakuraPmxDiffuse.value.toArray();
   const {applyPmxReferenceLighting}=await import('/static/js/pmx-reference-lighting.js');
   const shader=m.fragmentShader;applyPmxReferenceLighting(m,m.userData.MMD.authoredLighting);
   return {ok:loaded.ok,before,ambient:m.uniforms.sakuraPmxAmbient.value.toArray(),alpha:m.opacity,unchanged:shader===m.fragmentShader,authored:m.userData.MMD.authoredLighting.diffuse.slice(0,3)};
  });
  await page.waitForTimeout(1000);
  assert.equal(result.ok,true);assert.deepEqual(result.before,result.authored);assert.ok(result.ambient.every(v=>v>.59&&v<.61));assert.equal(result.alpha,1);assert.equal(result.unchanged,true);assert.deepEqual(shaderErrors,[]);
  // Visible result: front pink fabric must remain bright, and trim white.
  const colors=await page.evaluate(()=>{const v=auditViewer,gl=v.renderer.getContext();v._renderFrame();const pixels=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let pink=0,white=0;for(let i=0;i<pixels.length;i+=4){const [r,g,b,a]=pixels.subarray(i,i+4);if(a>200&&r>235&&g>130&&g<200&&b>170&&b<230)pink++;if(a>200&&r>240&&g>240&&b>240)white++;}return {pink,white};});
  assert.ok(colors.pink>1000,JSON.stringify(colors));assert.ok(colors.white>500,JSON.stringify(colors));
  console.log('PASS: authored PMX colour/ambient, opaque alpha, idempotent shader, bright pink fabric and white trim in real WebGL');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
