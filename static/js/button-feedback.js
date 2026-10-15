export function installButtonFeedback(){
    if(document.getElementById('sakura-button-feedback-style'))return;
    const style=document.createElement('style');style.id='sakura-button-feedback-style';
    style.textContent=`
    button,input[type=button],input[type=submit],[role=button]{-webkit-tap-highlight-color:transparent;transition:filter .12s ease,translate .12s ease}
    button:not(:disabled):active,[role=button]:active,input[type=button]:active,input[type=submit]:active{filter:brightness(1.2);translate:0 1px}
    .sakura-button-clicked{animation:sakura-button-tap .26s ease-out!important}
    button:focus-visible,[role=button]:focus-visible{outline:2px solid #7df7ee;outline-offset:3px}
    button[aria-busy=true]{cursor:progress;filter:brightness(1.08)}
    button[aria-busy=true]::before{content:'';display:inline-block;box-sizing:border-box;width:.85em;height:.85em;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;margin-right:.5em;vertical-align:-.05em;animation:sakura-button-spin .75s linear infinite}
    @keyframes sakura-button-tap{0%{filter:brightness(1.35);scale:.96}100%{filter:brightness(1);scale:1}}
    @keyframes sakura-button-spin{to{rotate:360deg}}
    @media(prefers-reduced-motion:reduce){.sakura-button-clicked{animation:none!important;filter:brightness(1.2)}button,input[type=button],input[type=submit],[role=button]{transition:none}button[aria-busy=true]::before{animation:none;border-right-color:currentColor}}
    `;document.head.append(style);
    const timers=new WeakMap();
    function feedback(event){
        const button=event.target?.closest?.('button,input[type=button],input[type=submit],[role=button]');
        if(!button||button.disabled||button.getAttribute('aria-disabled')==='true')return;
        if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;
        clearTimeout(timers.get(button));button.classList.add('sakura-button-clicked');
        timers.set(button,setTimeout(()=>{button.classList.remove('sakura-button-clicked');timers.delete(button);},280));
    }
    for(const type of ['pointerdown','click','keydown'])document.addEventListener(type,feedback,true);
}
