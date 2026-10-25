export function installCompactCompanionControls(getMicState){
    if(document.getElementById('compact-companion-mic'))return;
    const button=document.createElement('button');button.id='compact-companion-mic';button.type='button';
    button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/><path class="compact-mic-slash" d="M3 3l18 18"/></svg>';
    document.body.append(button);
    const sync=()=>{const enabled=!!getMicState();button.setAttribute('aria-pressed',String(enabled));button.setAttribute('aria-label',enabled?'Turn microphone off':'Turn microphone on');button.title=enabled?'Microphone on · click to turn off':'Microphone off · click to turn on';};
    button.onclick=()=>{document.getElementById('continuous-mic-btn')?.click();sync();};
    const observer=new MutationObserver(sync);const original=document.getElementById('continuous-mic-btn');if(original)observer.observe(original,{attributes:true,attributeFilter:['aria-pressed']});
    const timer=setInterval(sync,500);sync();window.addEventListener('pagehide',()=>{observer.disconnect();clearInterval(timer);},{once:true});
}
