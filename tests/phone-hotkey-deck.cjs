const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage({viewport:{width:360,height:800}});await page.setContent('<div id="expression"></div><p id="status"></p>');
 const source=fs.readFileSync('android/assets/mobile.js','utf8'),start=source.indexOf('const deckPanel='),end=source.indexOf('let visionStream=',start);assert(start>=0&&end>start);
 await page.addScriptTag({content:'window.$=id=>document.getElementById(id);let connected=false;window.calls=[];let fail=false;function status(text){$("status").textContent=text;}async function command(value){calls.push(value);if(fail)throw Error("Connection lost");return {ok:true};}'+source.slice(start,end)+';window.deck={render:renderHotkeyDeck,connect(){connected=true;},fail(){fail=true;}};'});
 await page.evaluate(()=>deck.render([{id:'slot1',label:'<img src=x>',kind:'scene'}]));assert.equal(await page.locator('#phone-hotkey-deck img').count(),0);
 await page.locator('#phone-hotkey-deck button').click();assert.equal(await page.evaluate(()=>calls.length),0);assert.match(await page.locator('#status').textContent(),/paired PC/);
 await page.evaluate(()=>deck.connect());await page.locator('#phone-hotkey-deck button').click();assert.deepEqual(await page.evaluate(()=>calls[0]),{type:'deck',id:'slot1'});
 await page.evaluate(()=>deck.fail());await page.locator('#phone-hotkey-deck button').click();assert.equal(await page.locator('#status').textContent(),'Connection lost');assert.equal(await page.locator('#phone-hotkey-deck button').isEnabled(),true);
 await page.evaluate(()=>deck.render([]));assert.equal(await page.locator('#phone-hotkey-deck').isVisible(),false);
 console.log('PASS: paired phone deck sends saved slot IDs only, renders safe text and recovers from connection failures');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
