const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage();let calendarRoute;
 await page.route('http://calendar.test/',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));
 await page.route('**/api/reminders',r=>r.fulfill({json:{items:[{id:'timer',kind:'timer',status:'ringing',label:'Tea'}]}}));
 await page.route('**/api/memory-archaeology/calendar-context',r=>{calendarRoute=r;});
 await page.goto('http://calendar.test/');
 await page.addScriptTag({content:fs.readFileSync('static/js/assistant-reminders.js','utf8').replace('export function','function')+';window.active=true;installReminders(()=>window.active);'});
 await page.waitForFunction(()=>!document.getElementById('reminder-alert').hidden);
 assert.match(await page.locator('#reminder-alert').textContent(),/Tea/,'Timer renders while the calendar request is still pending');
 await page.waitForFunction(()=>!!document.getElementById('reminder-alert'));
 assert(calendarRoute);
 await calendarRoute.fulfill({json:{nudge:{message:'Acme <img src=x onerror=alert(1)> proposal'}}});
 await page.waitForFunction(()=>document.querySelector('aside p')?.textContent.includes('Acme'));
 assert.equal(await page.locator('aside img').count(),0,'Calendar text is rendered safely');
 await page.getByRole('button',{name:'Revisit saves',exact:true}).click();
 assert.equal(await page.locator('aside').evaluate(el=>el.hidden),true);
 console.log('PASS: calendar offers are safe and independent of time-critical alarm polling');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
