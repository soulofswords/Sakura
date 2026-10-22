const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/game-laughter.js','utf8').replace('export async function','async function')+'\nthis.play=playGameLaughter;',ctx);
(async()=>{
 for(const style of ['laugh','laugh_bend']){
  let current=true,starts=0,stops=0,audio=0;
  const viewer={model:{},dance:{supported:()=>true,start:s=>{assert.equal(s,style);starts++;return true;},stop:()=>stops++}};
  const lip={stop:()=>audio++,playWithLipSync:async(url,onStart)=>{assert.equal(starts,0,'Pose waits for audio');assert.ok(url.split('?')[0].endsWith('.wav'));onStart();assert.equal(starts,1);}};
  assert.equal(await ctx.play(style,viewer,lip,()=>current),true);assert.equal(stops,1,'Pose fades out when the audio ends');stops=0;
  viewer.live2d={};assert.equal(await ctx.play(style,viewer,lip,()=>true),false);viewer.live2d=null;
  current=false;assert.equal(await ctx.play(style,viewer,lip,()=>current),false);
  current=true;starts=0;lip.playWithLipSync=async(url,onStart)=>{current=false;onStart();};
  assert.equal(await ctx.play(style,viewer,lip,()=>current),false);assert.equal(audio,1);assert.equal(starts,0);
  current=true;lip.playWithLipSync=async(url,onStart)=>{viewer.model={};onStart();};
  assert.equal(await ctx.play(style,viewer,lip,()=>current),false);assert.equal(audio,2);
  lip.playWithLipSync=async(url,onStart)=>{onStart();throw Error('audio failure');};
  await assert.rejects(ctx.play(style,viewer,lip,()=>current),/audio failure/);assert.equal(stops,1);
 }
 console.log('PASS: recorded laughter starts on playback, excludes Live2D, cancels stale/model-switch requests and cleans up failures');
})().catch(e=>{console.error(e);process.exitCode=1;});
