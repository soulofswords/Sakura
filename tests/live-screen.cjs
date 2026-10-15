const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let tick, now=1000, index=0, allowed=false;
const ctx={Date:{now:()=>now},setInterval(fn){tick=fn;return 1;},clearInterval(){tick=null;},
    window:{pywebview:{api:{async set_screen_access(value){allowed=value;},async screen_snapshot(){return '/9j/frame'+(++index);}}}},
    document:{createElement(){return {};}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/js/screen-share.js','utf8').replace('export default class ScreenShare','globalThis.ScreenShare = class ScreenShare'),ctx);
(async()=>{
    const screen=new ctx.ScreenShare();await screen.toggle();
    for(let i=0;i<6;i++){now+=333;await tick();}
    assert.equal(index,7,'capture continues without sending a chat request');
    const frames=Array.from(screen.recentFrames());assert.equal(frames.length,3);assert.equal(frames.at(-1),'/9j/frame7');
    assert.equal(await screen.snapshot(),'/9j/frame7');assert.equal(index,7,'AI consumes the buffered live frame');
    screen.stop();assert.equal(allowed,false);assert.deepEqual(Array.from(screen.recentFrames()),[]);assert.equal(tick,null);
    console.log('PASS: continuous capture, bounded chronological frame sequence, buffered reads and stop cleanup');
})().catch(error=>{console.error(error);process.exitCode=1;});
