const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const shareBlock=source.slice(source.indexOf('const screenShare = new ScreenShare('),source.indexOf("window.addEventListener('pagehide', () => screenShare.stop())"));
let callback,starts=0,stops=0;
const ctx={trackingOnly:false,vtuberEnabled:false,aiVtuberStarting:false,gameActive:false,screenWasEnabled:false,screenStartedMic:false,
    currentSettings:{llm_provider:'ollama'},reactionsEnabled:false,continuousMic:{enabled:false,stop(){stops++;this.enabled=false;}},
    startDesktopListening:async()=>{starts++;ctx.continuousMic.enabled=true;},
    screenReactBtn:{setAttribute(){}},screenViewBtn:{setAttribute(){}},screenViewStatus:{classList:{toggle(){}}},
    ScreenShare:class{constructor(fn){callback=fn;} enabled=false;}};
ctx.window={dispatchEvent(){}};ctx.Event=class{};
vm.createContext(ctx);vm.runInContext(shareBlock+'\nthis.share=screenShare;',ctx);
(async()=>{
    ctx.share.enabled=true;callback(true,false);await Promise.resolve();assert.equal(starts,1);
    ctx.continuousMic.enabled=false;callback(true,false);await Promise.resolve();assert.equal(starts,1,'manual mic off stays off');
    ctx.share.enabled=false;callback(false,false);assert.equal(stops,1);
    ctx.aiVtuberStarting=true;ctx.share.enabled=true;callback(true,false);await Promise.resolve();assert.equal(starts,1,'AI VTuber never starts microphone');
    const block=source.slice(source.indexOf('async function startDesktopListening('),source.indexOf('let chatReplyGeneration'));
    assert.ok(block.includes('continuousMic.start(selectedMicId)'),'must slice the real startDesktopListening, not an empty range');
    let selected;
    let agentMode=false;
    Object.assign(ctx,{selectedMicId:'chosen-microphone',autoGameEnabled:false,listeningStatus:{},document:{body:{classList:{contains:()=>agentMode}}}});
    ctx.continuousMic.start=async id=>{selected=id;};vm.runInContext(block,ctx);
    ctx.aiVtuberStarting=false;await ctx.startDesktopListening(true);assert.equal(selected,'chosen-microphone','explicit Listen uses the selected device');
    selected='unset';await ctx.startDesktopListening();assert.equal(selected,'chosen-microphone','explicit listening survives screen/background refresh');
    ctx.continuousMic.userRequested=false;selected='unset';await ctx.startDesktopListening();assert.equal(selected,'unset','a fresh automatic start still waits for opt-in');
    ctx.window={pywebview:{api:{set_wake_listener(){}}}};ctx.currentSettings.wake_word_enabled=true;
    let wakeSync=0;ctx.nativeWake={async sync(){wakeSync++;}};
    await ctx.startDesktopListening(true);assert.equal(selected,'chosen-microphone','explicit mic works with wake phrase enabled');assert.equal(wakeSync,1);
    selected=null;ctx.vtuberEnabled=true;await ctx.startDesktopListening(true);assert.equal(selected,null);
    ctx.vtuberEnabled=false;agentMode=true;await ctx.startDesktopListening(true);assert.equal(selected,null,'Agent mode must not restart Companion capture');
    const clickBlock=source.slice(source.indexOf("continuousMicBtn.addEventListener('click', async () => {"),source.indexOf('    installCompactCompanionControls('));
    let onClick,explicitStarts=0;
    const clickContext={continuousMicBtn:{addEventListener:(_,fn)=>{onClick=fn;}},speechInterrupt:{stop(){}},clearTimeout(){},interruptFollowupTimer:null,interruptFollowupUntil:0,speechInputUsed:false,temporaryFollowupMic:false,continuousMic:{enabled:false},nativeWake:{enabled:()=>true},wakeWordToggle:{checked:true},saveAppSettings:async()=>{},startDesktopListening:async explicit=>{if(explicit)explicitStarts++;}};
    vm.createContext(clickContext);vm.runInContext(clickBlock,clickContext);await onClick();
    assert.equal(explicitStarts,1,'One mic click switches wake listening to explicit recording');
    assert.equal(clickContext.wakeWordToggle.checked,false);
    console.log('PASS: selected microphone on explicit listen, automatic wake-word gate, explicit off preserved, screen stop and AI VTuber microphone exclusion');
})().catch(error=>{console.error(error);process.exitCode=1;});
