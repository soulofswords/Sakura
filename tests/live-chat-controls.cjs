const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();await page.setContent('<select id="cohost-service"><option value="youtube">YouTube</option><option value="twitch">Twitch</option><option value="both">YouTube + Twitch</option></select><input id="youtube-chat-link"><label id="cohost-twitch-link-group" hidden><input id="cohost-twitch-link"></label><details id="cohost-twitch-setup"><summary>Twitch</summary><input></details><select id="reader-service"><option value="youtube">YouTube</option><option value="twitch">Twitch</option><option value="both">YouTube + Twitch</option></select><input id="reader-chat-link"><label id="reader-twitch-link-group" hidden><input id="reader-twitch-link"></label><details id="reader-twitch-setup"><summary>Authorization</summary><input></details>');
await page.addScriptTag({content:fs.readFileSync('static/js/live-chat-controls.js','utf8').replace('export function','function')+';installLiveChatControls();'});
assert.equal(await page.locator('#reader-twitch-setup').isVisible(),false);await page.selectOption('#reader-service','twitch');assert.equal(await page.locator('#reader-twitch-setup').isVisible(),true);assert.equal(await page.locator('#reader-twitch-setup').getAttribute('open'),'');
await page.fill('#reader-chat-link','https://youtube.com/watch?v=example');assert.equal(await page.locator('#reader-service').inputValue(),'youtube');await page.fill('#reader-chat-link','https://twitch.tv/streamer');assert.equal(await page.locator('#reader-service').inputValue(),'twitch');
await page.selectOption('#cohost-service','twitch');assert.equal(await page.locator('#cohost-twitch-setup').isVisible(),true);await page.fill('#youtube-chat-link','https://youtube.com/watch?v=x');assert.equal(await page.locator('#cohost-service').inputValue(),'youtube');
for(const prefix of ['reader','cohost']){
 await page.selectOption('#'+prefix+'-service','both');
 assert.equal(await page.locator('#'+prefix+'-twitch-setup').isVisible(),true);
 assert.equal(await page.locator('#'+prefix+'-twitch-link-group').isVisible(),true);
 await page.fill(prefix==='reader'?'#reader-chat-link':'#youtube-chat-link','https://youtube.com/watch?v=x');
 assert.equal(await page.locator('#'+prefix+'-service').inputValue(),'both','Pasting YouTube must not switch dual mode off');
 await page.selectOption('#'+prefix+'-service','youtube');assert.equal(await page.locator('#'+prefix+'-twitch-link-group').isVisible(),false);
}
console.log('PASS: YouTube/Twitch selection, pasted-link detection and visible Twitch authorization');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
