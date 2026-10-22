const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const elements={'app-brand-logo':{},'app-favicon':{}},splashes={},calls=[];
const ctx={window:{SAKURA_EDITION:'companion',pywebview:{api:{set_brand_mode:value=>calls.push(value)}}},document:{getElementById:id=>elements[id],querySelector:selector=>splashes[selector]??= {}},console};
vm.runInNewContext(fs.readFileSync('static/js/app-branding.js','utf8').replace(/export /g,'')+'\nthis.update=updateAppBrand;',ctx);
for(const edition of ['companion','combined','vtuber'])for(const tracking of [false,true]){
    ctx.window.SAKURA_EDITION=edition;ctx.update(tracking);
    const expected=edition==='vtuber'?'vtuber-app.png':tracking?'companion-vtuber.png':'desktop-companion.png';
    assert.equal(elements['app-brand-logo'].src,'/static/assets/'+expected+'?v=flower79');
    assert.equal(elements['app-favicon'].href,elements['app-brand-logo'].src);
    for(const id of ['desktop-companion-splash','model-upload-splash']){
        assert.equal(splashes['#'+id+' img'].src,elements['app-brand-logo'].src);
        assert.equal(splashes['#'+id+' strong'].textContent,edition==='vtuber'?'Sakura VTuber':tracking?'Sakura Companion · VTuber':'Sakura Companion');
    }
    assert.equal(calls.at(-1),tracking);
}
console.log('PASS: all product/mode logo mappings, titlebar, favicon, splash and native mode updates');
