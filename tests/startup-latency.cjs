const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/js/app.js','utf8');
const begin=source.indexOf('    // Load only the character on the first-paint path;');
const end=source.indexOf('    // 4. Apply saved audio output device',begin);
const reveal=source.indexOf('    await finishStartupPresentation(viewer);',end);
const after=source.indexOf('    if(!trackingOnly)try{',reveal);
assert.ok(begin>0&&end>begin&&reveal>end&&after>reveal);
const events=[],never=new Promise(()=>{});
const context={currentSettings:{},trackingOnly:false,viewer:{setVtuberTrackingMode(){}},document:{body:{classList:{toggle(){}}}},
loadAppSettings:async()=>events.push('settings'),updateTransparencyShortcut(){},updateAppBrand(){},loadModelsList:async()=>events.push('model'),
loadVoicesList:()=>{events.push('voices');return never;},refreshAudioDevices:()=>{events.push('audio');return never;},
finishStartupPresentation:async()=>events.push('visible'),console};
vm.runInNewContext('(async()=>{'+source.slice(begin,end)+source.slice(reveal,after)+'})()',context).then(()=>{
assert.deepEqual(events,['settings','model','visible','voices','audio']);
console.log('PASS: character ready reveals window while voice and device enumeration remain unresolved.');
}).catch(e=>{console.error(e);process.exitCode=1;});
