const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
const page=await browser.newPage();await page.route('http://defaults.test/**',r=>r.fulfill({contentType:'text/html',body:'<button id="screen"></button><button id="reaction" aria-pressed="false"></button><button id="game" aria-pressed="false"></button><p id="status"></p><div id="voice-preset-grid"></div>'}));await page.goto('http://defaults.test/');
await page.addScriptTag({content:fs.readFileSync('static/js/companion-defaults.js','utf8').replace('export function','function')+fs.readFileSync('static/js/character-voice.js','utf8').replace('export function','function')});
await page.evaluate(()=>{window.blocked=true;window.captures=0;window.pywebview={api:{set_screen_access(){}}};window.sakuraCompanionDefaultsReady=true;window.screenState={enabled:false,async toggle(){captures++;this.enabled=!this.enabled;dispatchEvent(new Event('sakura-screen-state'));}};
const $=id=>document.getElementById(id);$('screen').onclick=()=>screenState.toggle();$('reaction').onclick=()=>{$('reaction').setAttribute('aria-pressed',String($('reaction').getAttribute('aria-pressed')!=='true'));};$('game').onclick=()=>{$('game').setAttribute('aria-pressed',String($('game').getAttribute('aria-pressed')!=='true'));};
installCompanionDefaults({blocked:()=>blocked,screen:screenState,screenButton:$('screen'),reactionButton:$('reaction'),gameButton:$('game'),status:$('status')});});
assert.equal(await page.evaluate(()=>captures),0,'Tracking-only mode never captures');
await page.evaluate(()=>{blocked=false;dispatchEvent(new Event('sakura-companion-ready'));});await page.waitForFunction(()=>captures===1);
assert.equal(await page.locator('#reaction').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#game').getAttribute('aria-pressed'),'true');
await page.locator('#screen').click();assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('sakura-companion-defaults-v1')).screen),false,'Explicit screen off stays saved');
await page.evaluate(()=>{window.model='female-model';window.voice='kokoro_af_bella';window.applied=[];installCharacterVoice({getModel:()=>model,getVoice:()=>voice,blocked:()=>false,applyVoice:async value=>{voice=value;applied.push(value);}});});
await page.selectOption('#character-voice-profile','soft');assert.equal(await page.evaluate(()=>voice),'kokoro_af_heart');
await page.evaluate(()=>{model='male-model';dispatchEvent(new Event('sakura-character-loaded'));});await page.selectOption('#character-voice-profile','bold');assert.equal(await page.evaluate(()=>voice),'kokoro_am_michael');
await page.evaluate(()=>{model='female-model';dispatchEvent(new Event('sakura-character-loaded'));});assert.equal(await page.evaluate(()=>voice),'kokoro_af_heart');
await page.evaluate(()=>{voice='kokoro_hf_alpha_hindi';dispatchEvent(new Event('sakura-character-loaded'));});assert.equal(await page.evaluate(()=>voice),'kokoro_hf_alpha_hindi','Language choice is preserved');
console.log('PASS: Companion defaults, VTuber capture exclusion, saved screen off and per-character voices with language preservation');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
