const fs=require('fs'),assert=require('assert/strict');
const source=fs.readFileSync('static/js/model-viewer.js','utf8');
const body=source.slice(source.indexOf('    _animateCharacter(delta, elapsed) {')+ '    _animateCharacter(delta, elapsed) {'.length,source.indexOf('            // Keep a little authored life under the tracked pose;'));
const model={},events=[];let resets=0;
const viewer={model,userTracking:true,userTrackingSample:{},physics:{},avatarRetarget:{apply(){throw Error('Bad hand packet');},reset(){resets++;}}};
new Function('window','CustomEvent','console','delta','elapsed',body+'}').call(viewer,{dispatchEvent:e=>events.push(e)},class{constructor(type,init){this.type=type;this.detail=init.detail;}},{error(){}},1/60,0);
assert.equal(viewer.model,model,'Tracking exceptions preserve the loaded model');
assert.equal(viewer.userTracking,false);assert.equal(resets,1);assert.equal(events[0].type,'sakura-tracking-error');
console.log('PASS: failing hand retarget pauses tracking, resets the rig and preserves the loaded avatar.');
