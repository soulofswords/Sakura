const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();
  await page.setContent('<nav id="agent-studio-nav"><div id="agent-recent-tasks"><div id="tasks"><div class="task-row"><button>Long task title<br>with several lines<br>of text</button><button class="task-menu-button" aria-label="Task actions"></button></div></div></div></nav>');
  await page.addStyleTag({content:fs.readFileSync('static/css/agent-studio.css','utf8')});
  const box=await page.locator('.task-menu-button').evaluate(el=>{
   const r=el.getBoundingClientRect(),row=el.parentElement.getBoundingClientRect(),s=getComputedStyle(el);
   return {width:r.width,height:r.height,offset:(r.top+r.bottom-row.top-row.bottom)/2,justify:s.justifyContent};
  });
  assert.equal(box.width,32);assert.equal(box.height,32);
  assert.ok(Math.abs(box.offset)<1);assert.equal(box.justify,'center');
  console.log('PASS: multiline task menu has a centred dot track and square centred hitbox.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
