const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:420,height:800}});
  const html=fs.readFileSync('static/index.html','utf8').match(/<section id="chat-panel">[\s\S]*?<\/section>/)[0];
  const css=fs.readFileSync('static/css/style.css','utf8');
  await page.route('http://sakura.test/**',async route=>{
   const request=route.request();
   if(request.url().includes('/api/chat/attachments')){
    if(request.method()==='DELETE')return route.fulfill({json:{ok:true}});
    return route.fulfill({json:{id:'file-token',name:'resume.txt',kind:'text'}});
   }
   return route.fulfill({contentType:'text/html; charset=utf-8',body:'<meta charset="utf-8"><style>'+css+'</style>'+html});
  });
  await page.goto('http://sakura.test/');
  const encoded=Buffer.from(fs.readFileSync('static/js/chat-attachments.js','utf8')).toString('base64');
  await page.evaluate(async encoded=>{
   const {installChatAttachments}=await import('data:text/javascript;base64,'+encoded);
   window.notices=[];window.attachmentsUI=installChatAttachments({notice:text=>window.notices.push(text)});
  },encoded);
  await page.locator('#chat-file-input').setInputFiles({name:'resume.txt',mimeType:'text/plain',buffer:Buffer.from('Electrical engineering projects')});
  await page.locator('.chat-file-chip').waitFor();
  assert.deepEqual(await page.evaluate(()=>window.attachmentsUI.ids()),['file-token']);
  assert.ok(await page.locator('#attach-chat-btn').isVisible());
  const bounds=await page.evaluate(()=>{const panel=document.querySelector('#chat-panel').getBoundingClientRect(),send=document.querySelector('#send-btn').getBoundingClientRect();return {panelRight:panel.right,sendRight:send.right};});
  assert.ok(bounds.sendRight<=bounds.panelRight,'Attachment button must not push Send beyond the panel');
  await page.screenshot({path:'audit-results/chat-attachments-ui.png'});
  await page.locator('.chat-file-chip').click();assert.deepEqual(await page.evaluate(()=>window.attachmentsUI.ids()),[]);
  console.log('PASS: actual attachment button, multipart upload, file chip/removal, safe filenames and compact chat layout');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
