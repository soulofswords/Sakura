const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');

(async()=>{
 const html=execFileSync('venv/Scripts/python.exe',['-c','from tools.jio_library_owner import PAGE; print(PAGE)'],{encoding:'utf8'});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();const errors=[],calls=[];
  page.on('pageerror',e=>errors.push(e.message));
  let state={message:'Ready.',otpRequested:false,needsPassphrase:false,account:{},folderCount:0,connected:false};
  await page.route('http://owner.test/**',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   assert.equal(request.headers()['x-sakura-owner'],'test-capability');
   const body=request.postDataJSON();calls.push({path:url.pathname,body});
   if(url.pathname==='/api/send-otp')state={...state,otpRequested:true,message:'Enter the OTP.'};
   if(url.pathname==='/api/verify-otp'){
    state={...state,otpRequested:false,otpAccepted:true,canInspect:true,account:{emailId:'owner@example.com'},folderCount:0,message:'OTP accepted.'};
    return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Jio rejected finding the live2d folder (HTTP 400, code TEST400).',state})});
   }
   if(url.pathname==='/api/inspect')state={...state,folderCount:1,folder:'live2d',message:'Confirm the destination.'};
   if(url.pathname==='/api/confirm')state={...state,connected:true,message:'Connection saved. No files uploaded yet.'};
   if(url.pathname==='/api/reset-login')state={message:'Request a fresh OTP.',otpAccepted:false,otpRequested:false,canInspect:false,needsPassphrase:false,account:{},folderCount:0,connected:false};
   return route.fulfill({contentType:'application/json',body:JSON.stringify(state)});
  });
  await page.goto('http://owner.test/#test-capability');
  await page.waitForFunction(()=>document.getElementById('message').textContent==='Ready.');
  assert.equal(new URL(page.url()).hash,'');
  assert.equal(await page.locator('#account').isVisible(),false);
  assert.equal(await page.locator('#verify').isVisible(),false);
  await page.locator('#identity').fill('owner@example.com');
  await page.getByRole('button',{name:'Send OTP',exact:true}).click();
  await page.locator('#otp').waitFor({state:'visible'});
  await page.locator('#otp').fill('123456');
  await page.getByRole('button',{name:'Verify OTP',exact:true}).click();
  await page.waitForFunction(()=>document.getElementById('message').textContent.includes('TEST400'));
  assert.equal(await page.locator('#verify').isVisible(),false);
  assert.equal(await page.locator('#send').isVisible(),false);
  await page.getByRole('button',{name:'Retry account / folder check',exact:true}).click();
  await page.locator('#confirm').waitFor({state:'visible'});
  assert.match(await page.locator('#who').textContent(),/owner@example.com/);
  assert.match(await page.locator('#folder').textContent(),/My Files \/ live2d/);
  assert.equal(await page.locator('#otp').inputValue(),'');
  await page.locator('#confirm').click();
  await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Connection saved'));
  assert.equal(await page.locator('#confirm').isVisible(),false);
  assert.equal(calls.filter(c=>c.path==='/api/confirm').length,1);
  await page.reload();
  await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Connection saved'));
  assert.equal(calls.filter(c=>c.path==='/api/confirm').length,1);
  assert.equal(calls.some(c=>/upload|publish/.test(c.path)),false);
  await page.getByRole('button',{name:'Sign in again',exact:true}).click();
  await page.locator('#send').waitFor({state:'visible'});
  assert.equal(await page.locator('#account').isVisible(),false);
  assert.deepEqual(errors,[]);
  console.log('PASS: owner login, private OTP entry, account/folder confirmation, no upload actions.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
