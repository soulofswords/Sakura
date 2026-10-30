const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const page=await browser.newPage();await page.route('http://alpha.test/**',route=>{
  const relative=new URL(route.request().url()).pathname.slice(1),file=path.resolve(relative);
  if(!file.startsWith(path.resolve('static')+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
  return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':'text/html',body:fs.readFileSync(file)});
 });
 await page.goto('http://alpha.test/static/library-audit.html?no-capture');
 const result=await page.evaluate(async()=>{
  const THREE=await import('three'),{appearanceStats,appearanceLoss}=await import('/static/js/pmx-appearance-match.js?v=alpha-proof');
  const renderer=new THREE.WebGLRenderer({alpha:true}),scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=2;
  const material=new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.5,depthWrite:false});
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);scene.add(mesh);
  const target=new THREE.WebGLRenderTarget(32,32);target.texture.colorSpace=THREE.SRGBColorSpace;renderer.setRenderTarget(target);
  function capture(alpha){renderer.setClearColor(0,alpha);renderer.clear();renderer.render(scene,camera);const pixels=new Uint8Array(32*32*4);renderer.readRenderTargetPixels(target,0,0,32,32,pixels);return {pixels,width:32,height:32};}
  const transparent=capture(0),black=capture(1),score=appearanceLoss(appearanceStats(transparent),appearanceStats(black));
  const result={transparent:Array.from(transparent.pixels.slice(0,4)),black:Array.from(black.pixels.slice(0,4)),score};
  target.dispose();mesh.geometry.dispose();material.dispose();renderer.dispose();return result;
 });
 console.log(JSON.stringify(result));assert.deepEqual(result.transparent.slice(0,3),result.black.slice(0,3));assert.equal(result.score,0);
 console.log('PASS: actual translucent WebGL readback matches black-backed reference without applying alpha twice');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
