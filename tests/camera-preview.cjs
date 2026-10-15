const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/camera-preview.js','utf8').replace(/export /g,'')+'\nthis.draw=drawCameraPreview;',ctx);
let calls=[];const context={canvas:{width:640,height:360},fillRect(...args){calls.push(['cover',...args]);},drawImage(){calls.push(['video']);},beginPath(){},arc(){calls.push(['point']);},fill(){},moveTo(){},lineTo(){},stroke(){}};
const video={readyState:2},face={landmarks:[{x:.4,y:.3},{x:.6,y:.6}]};
ctx.draw(context,video,{face},true);assert.equal(calls[1][0],'video');assert.equal(calls[2][0],'cover','Face covered after camera copy and before tracking points');assert.equal(calls[3][0],'point');
calls=[];ctx.draw(context,video,{face:{landmarks:[]}},true);assert.ok(!calls.some(c=>c[0]==='video'),'Lost face must never reveal raw camera image');
calls=[];ctx.draw(context,video,null,false);assert.ok(calls.some(c=>c[0]==='video'),'User can explicitly disable privacy');
calls=[];ctx.draw(context,null,{face},true);assert.ok(calls.some(c=>c[0]==='point'));assert.ok(!calls.some(c=>c[0]==='video'),'Phone points work without video transfer');
console.log('PASS: privacy-masked camera overlay, face-loss protection, optional raw preview and phone tracking without camera video');
