export function brandAsset(edition,tracking){
    return edition==='vtuber'?'vtuber-app.png':tracking?'companion-vtuber.png':'desktop-companion.png';
}
export function updateAppBrand(tracking){
    const edition=window.SAKURA_EDITION||'companion';
    const src='/static/assets/'+brandAsset(edition,tracking)+'?v=flower79';
    const logo=document.getElementById('app-brand-logo');
    if(logo){logo.src=src;logo.alt=edition==='vtuber'?'Sakura VTuber':tracking?'Sakura Companion · VTuber mode':'Sakura Companion';}
    const favicon=document.getElementById('app-favicon');if(favicon)favicon.href=src;
    for(const id of ['desktop-companion-splash','model-upload-splash']){
        const splash=document.querySelector('#'+id+' img');if(splash){splash.src=src;splash.alt=logo?.alt||'Sakura';}
        const title=document.querySelector('#'+id+' strong');if(title)title.textContent=edition==='vtuber'?'Sakura VTuber':tracking?'Sakura Companion · VTuber':'Sakura Companion';
    }
    const api=window.pywebview?.api;
    if(api?.set_brand_mode)Promise.resolve(api.set_brand_mode(!!tracking)).catch(console.warn);
}
