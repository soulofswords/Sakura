const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:700,height:850}}),shaderErrors=[];
  let brokenTextures=false;
  page.on('console',message=>{if(message.type()==='error'&&/Shader Error|VALIDATE_STATUS|shader error/i.test(message.text()))shaderErrors.push(message.text());});
  await page.route('http://pmx.test/**',route=>{
   const url=new URL(route.request().url()),relative=decodeURIComponent(url.pathname).slice(1),file=path.resolve(relative);
   if(!file.startsWith(process.cwd()+path.sep)||!['static','models'].includes(relative.split('/')[0]))return route.fulfill({status:404,body:''});
   // Simulate unreadable artwork; do not depend on corrupt owner files remaining
   // corrupt after they have been recovered from their intact originals.
   if(brokenTextures&&/Gratia_MMD\/tex\/T_GratiaDefault_(Face01|Skin01|Hair01|Hat01|Pupil01|EyeTrans01|Special01)_A_D\.png$/i.test(relative))return route.fulfill({contentType:'image/png',body:Buffer.alloc(32)});
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
  const restored=await page.evaluate(async()=>{
   const loaded=await auditModel('pmx/Silver palace/Gratia_MMD/Gratia.pmx');
   return {ok:loaded.ok,missing:auditViewer.pmxReferenceAudit?.missingAssets,repairs:auditViewer.pmxReferenceAudit?.repaired.filter(row=>row.kinds.includes('diffuse'))};
  });
  assert.equal(restored.ok,true);assert.deepEqual(restored.missing,[]);assert.deepEqual(restored.repairs,[]);
  console.log('PASS: recovered Gratia loads its real artwork without diffuse or optional-map fallbacks');
  const backSnapshot=await page.evaluate(()=>{
   const viewer=auditViewer;
   viewer.camera.position.copy(viewer.controls.target).add(new viewer.camera.position.constructor(0,0,-30));
   viewer.camera.lookAt(viewer.controls.target);viewer.camera.zoom=1.7;viewer.camera.updateProjectionMatrix();
   const state=()=>JSON.stringify({position:viewer.camera.position.toArray(),rotation:viewer.camera.quaternion.toArray(),zoom:viewer.camera.zoom,aspect:viewer.camera.aspect,far:viewer.camera.far,target:viewer.controls.target.toArray(),model:viewer.model.position.toArray()});
   const before=state(),capture=viewer.captureSpoutFrame;
   let facing,inside;
   viewer.captureSpoutFrame=function(size){
    const box=this._visibleModelBounds(this.model),P=this.camera.position.constructor;
    facing=this.camera.position.z<this.controls.target.z;
    inside=true;
    for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
     const point=new P(x,y,z).project(this.camera);if(Math.abs(point.x)>1||Math.abs(point.y)>1)inside=false;
    }
    return capture.call(this,size);
   };
   try{const frame=viewer.captureTextureDiagnosticFrame(960);return {same:state()===before,facing,inside,width:frame.width,height:frame.height};}
   finally{viewer.captureSpoutFrame=capture;}
  });
  assert.equal(backSnapshot.same,true,'Full-body capture restores the user camera and zoom');assert.equal(backSnapshot.facing,true,'Back stays back');assert.equal(backSnapshot.inside,true,'Full model bounds fit inside the image');assert.equal(backSnapshot.width,720);assert.equal(backSnapshot.height,960);
  console.log('PASS: full-model back snapshot fits all bounds and preserves camera, target and zoom');
  const stockings=await page.evaluate(async()=>{
   const loaded=await auditModel('pmx/Miku universe/Miku/TDA Traditional Miku/Miku #2.pmx');
   const viewer=auditViewer,materials=viewer.model.material,visibility=materials.map(m=>m.visible);
   try{
    const material=materials.find(m=>m.name==='Skin02');
    for(const each of materials)each.visible=each===material;
    const frame=viewer.captureTextureDiagnosticFrame(960);let total=0,count=0;
    for(let i=0;i<frame.pixels.length;i+=4)if(frame.pixels[i+3]>200){total+=frame.pixels[i]+frame.pixels[i+1]+frame.pixels[i+2];count++;}
    return {ok:loaded.ok,pixels:count,mean:total/Math.max(count*3,1),litAmbient:material.uniforms.sakuraPmxLitAmbient.value,
     ambient:material.userData.MMD.authoredLighting.ambient,authoredAmbient:material.uniforms.sakuraPmxAmbient.value.toArray()};
   }finally{materials.forEach((material,i)=>material.visible=visibility[i]);}
  });
  // The flat fill saturates a normal 0.5-ambient material and leaves a
  // zero-ambient one black; the visible mean is then only whatever specular the
  // current pose catches, so assert the law the shader was handed, not a
  // brightness that moves with the camera.
  assert.equal(stockings.ok,true);assert.deepEqual(stockings.ambient,[0,0,0]);
  assert.deepEqual(stockings.authoredAmbient,[0,0,0]);assert.equal(stockings.litAmbient,0);
  assert.ok(stockings.pixels>1000,'the stocking surfaces are still drawn');
  assert.ok(stockings.mean<130,JSON.stringify(stockings));
  console.log('PASS: Traditional Miku #2 zero-ambient stockings stay dark without recolouring their white source atlas');
  // Clear image/loader state before independently exercising the corrupt-input case.
  brokenTextures=true;await page.reload();await page.waitForFunction(()=>window.auditReady);
  // A zero-filled texture file is the worst thing an upload can carry: the name is
  // right, the bytes exist, nothing decodes, and every surface referencing it
  // multiplies by black. The route above simulates seven broken Gratia files.
  const broken=await page.evaluate(async()=>{
   const loaded=await auditModel('pmx/Silver palace/Gratia_MMD/Gratia.pmx');
   const undecodable=[];
   auditViewer.model.traverse(mesh=>{for(const m of (Array.isArray(mesh.material)?mesh.material:[mesh.material])){
    if(!m?.isMMDToonMaterial||!m.map)continue;
    const img=m.map.image,width=img?.naturalWidth||img?.width,height=img?.naturalHeight||img?.height;
    if(!(width>0&&height>0))undecodable.push(m.name);
   }});
   const v=auditViewer,gl=v.renderer.getContext();v.desktopMode=true;v._autoFrame(v.model);v._renderFrame();v.desktopMode=false;
   const px=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
   gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,px);
   let lit=0,bright=0;
   for(let i=0;i<px.length;i+=4){const[r,g,b,a]=px.subarray(i,i+4);if(a>200){lit++;if(r>200&&g>200&&b>200)bright++;}}
   return {ok:loaded.ok,notice:loaded.notice,errors:loaded.errors,undecodable,
    missing:(v.pmxReferenceAudit?.missingAssets||[]).map(entry=>({name:entry.name,kinds:entry.kinds})),lit,bright};
  });
  assert.deepEqual(broken.undecodable,[],'every bound diffuse slot must hold a decodable image');
  // 7 unreadable files back 11 materials, so the report counts surfaces, not paths.
  assert.equal(broken.missing.length,11,JSON.stringify(broken.missing));
  assert.ok(broken.missing.every(entry=>entry.kinds.includes('diffuse')),JSON.stringify(broken.missing));
  assert.match(broken.notice||'',/11 surface\(s\)/);
  assert.match(broken.notice||'',/T_GratiaDefault_Face01_A_D\.png/);
  assert.match(broken.notice||'',/and 4 more/);
  assert.ok(broken.bright>broken.lit*0.05,JSON.stringify({lit:broken.lit,bright:broken.bright}));
  assert.deepEqual(broken.errors,[]);
  console.log(`PASS: seven zero-filled textures named, bound to neutral and reported (${broken.bright}/${broken.lit} bright pixels, no black silhouette)`);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
