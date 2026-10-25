const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const THREE=await import('../static/vendor/three/build/three.module.js');
 const source=fs.readFileSync('static/js/model-viewer.js','utf8');
 const body=source.slice(source.indexOf('    captureSpoutFrame(maxSize=720) {')+'    captureSpoutFrame(maxSize=720) {'.length,source.indexOf('\n    releaseSpoutFrame()')).replace(/\}\s*$/,'');
 const capture=new Function('THREE','maxSize',body);
 let target=null;const originalViewport=new THREE.Vector4(2,3,600,400),originalScissor=new THREE.Vector4(1,2,500,300);
 const renderer={capabilities:{maxSamples:4},getDrawingBufferSize:v=>v.set(1920,1080),getRenderTarget:()=>target,getViewport:v=>v.copy(originalViewport),getScissor:v=>v.copy(originalScissor),getScissorTest:()=>true,getClearColor:c=>c.set(0x123456),getClearAlpha:()=>1,setClearColor(){},setRenderTarget:t=>target=t,setViewport(){},setScissor(){},setScissorTest(){},clear(){},render(){},readRenderTargetPixels(t,x,y,w,h,p){p[3]=255;}};
 const viewer={model:{},camera:{aspect:16/9},scene:{background:null},renderer};
 let frame=capture.call(viewer,THREE,0);
 assert.equal(frame.width,1920);assert.equal(frame.height,1080);assert.equal(viewer._spoutTarget.samples,4);
 assert.equal(target,null,'Capture restores the onscreen render target');
 frame=capture.call(viewer,THREE,2560);assert.equal(frame.width,2560);assert.equal(frame.height,1440);
 renderer.getDrawingBufferSize=v=>v.set(3840,2160);frame=capture.call(viewer,THREE,0);assert.equal(frame.width,2560,'Native mode bounds memory use');
 console.log('PASS: native Full HD, QHD, multisample antialiasing and render target restoration.');
})().catch(e=>{console.error(e);process.exitCode=1;});
