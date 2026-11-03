// Shared appearance for the phone controls and the embedded avatar stage.
(() => {
    const choices=['light','dark','system'];
    const system=matchMedia('(prefers-color-scheme: dark)');
    let mode='system';
    try {const saved=localStorage.getItem('sakura_ui_theme');if(choices.includes(saved))mode=saved;} catch (_) {}
    function apply(){
        let dark=system.matches;
        try{if(typeof window.Sakura?.systemDarkAppearance==='function')dark=window.Sakura.systemDarkAppearance();}catch(_){}
        const theme=mode==='system'?(dark?'dark':'light'):mode;
        document.documentElement.dataset.uiTheme=theme;
        document.documentElement.style.colorScheme=theme;
        document.querySelectorAll('[data-mobile-appearance]').forEach(select=>select.value=mode);
    }
    function change(value){
        if(!choices.includes(value))return;
        mode=value;try{localStorage.setItem('sakura_ui_theme',mode);}catch(_){}
        apply();
        document.querySelectorAll('iframe').forEach(frame=>{try{frame.contentWindow.postMessage({type:'sakura-appearance',mode},'https://models.sakura.invalid');}catch(_){}});
    }
    function picker(){
        const section=document.createElement('section');section.className='mobile-appearance';section.setAttribute('aria-label','Appearance');
        const label=document.createElement('label');label.textContent='Appearance';
        const select=document.createElement('select');select.dataset.mobileAppearance='';select.setAttribute('aria-label','Appearance theme');
        for(const value of choices)select.add(new Option(value[0].toUpperCase()+value.slice(1),value));
        select.value=mode;select.onchange=()=>change(select.value);label.append(select);section.append(label);
        const help=document.createElement('small');help.textContent='System follows your phone’s light or dark theme. Saved automatically.';section.append(help);
        return section;
    }
    apply();
    system.addEventListener('change',()=>{if(mode==='system')apply();});
    window.addEventListener('focus',()=>{if(mode==='system')apply();});
    window.addEventListener('storage',event=>{if(event.key==='sakura_ui_theme'&&choices.includes(event.newValue)){mode=event.newValue;apply();}});
    window.addEventListener('message',event=>{if(event.origin==='https://appassets.androidplatform.net'&&event.source===parent&&event.data?.type==='sakura-appearance'&&choices.includes(event.data.mode)){mode=event.data.mode;apply();}});
    // A renderer created after the picker changed still receives the current choice.
    window.addEventListener('message',event=>{if(event.origin==='https://models.sakura.invalid'&&event.data?.type==='avatar-ready'&&[...document.querySelectorAll('iframe')].some(frame=>frame.contentWindow===event.source))event.source.postMessage({type:'sakura-appearance',mode},event.origin);});
    document.addEventListener('DOMContentLoaded',()=>{
        if(!document.getElementById('app-modes'))return; // Avatar iframe has no controls.
        const home=picker();home.id='mobile-appearance-home';document.getElementById('app-modes').after(home);
        document.getElementById('local-stage-panel')?.prepend(picker());
        apply();
    },{once:true});
})();
