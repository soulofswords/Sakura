const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const source=fs.readFileSync('static/js/pmx-appearance-match.js','utf8').replace(/^import .*;\r?\n/,'');
 const shim=`const PMX_RENDER_CONTROLS=[['brightness','Brightness',0,2,1]];
 const normalizePmxAppearance=v=>({brightness:v?.brightness??1});
 const applyPmxAppearance=(root,value)=>root.settings=value;
 const requestAnimationFrame=callback=>callback();`;
 const {fitPmxAppearance,appearanceStats}=await import('data:text/javascript;base64,'+Buffer.from(shim+source).toString('base64'));
 const frame=(value,alpha=255)=>({pixels:Uint8ClampedArray.from(Array.from({length:100},()=>[value,value,value,alpha]).flat())});
 // Blended WebGL RGB and native black-backed RGB agree regardless of output alpha.
 assert.deepEqual(appearanceStats(frame(100,128)),appearanceStats(frame(100)));
 const hidden={visible:false},shown={visible:true},root={material:[hidden,shown],settings:{brightness:.5},traverse(fn){fn(this);}};
 const viewer={model:root,captureTextureDiagnosticFrame(){return frame(Math.round(100*root.settings.brightness));}};
 const visibility=root.material.map(m=>m.visible);
 const hiddenResult=await fitPmxAppearance(viewer,frame(100),{brightness:.5},{parts:[{material:0,frame:frame(100)}]});
 assert.equal(hiddenResult.materials,0);assert.equal(hiddenResult.skippedMaterials,1);assert.equal(hiddenResult.improved,true);
 assert.deepEqual(root.material.map(m=>m.visible),visibility);
 const empty=await fitPmxAppearance(viewer,frame(100),{brightness:.5},{parts:[]});
 assert.equal(empty.materials,0);assert.equal(empty.improved,true);
 // A front-facing reference part may be occluded in the current renderer pose.
 viewer.captureTextureDiagnosticFrame=()=>shown.visible?frame(Math.round(100*root.settings.brightness)):frame(0,0);
 hidden.visible=true;
 const occluded=await fitPmxAppearance(viewer,frame(100),{brightness:.5},{parts:[{material:0,frame:frame(100)}]});
 assert.equal(occluded.skippedMaterials,1);assert.equal(occluded.improved,true);
 // Improving the sampled part may not worsen the unsampled composite.
 hidden.visible=false;
 // Distinguish isolation from composite with a third visible material.
 const other={visible:true};root.material.push(other);
 viewer.captureTextureDiagnosticFrame=()=>frame(Math.round(other.visible?100*root.settings.brightness:50*root.settings.brightness));
 const guarded=await fitPmxAppearance(viewer,frame(100),{brightness:1},{parts:[{material:1,frame:frame(100)}]});
 assert.equal(guarded.improved,false);assert.equal(guarded.settings.brightness,1);
 assert.deepEqual(root.material.map(m=>m.visible),[false,true,true]);
 console.log('PASS: hidden/occluded parts, translucent whole-frame fallback, whole-model non-regression and visibility restoration');
})().catch(error=>{console.error(error);process.exitCode=1;});
