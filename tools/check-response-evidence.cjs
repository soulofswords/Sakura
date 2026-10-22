const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();await page.setContent('<div id="message"></div>');
  const source=fs.readFileSync('static/js/response-evidence.js','utf8');
  await page.evaluate(async source=>{
   const {appendEvidence}=await import('data:text/javascript;base64,'+btoa(source));
   appendEvidence(document.querySelector('#message'),{statements:[{text:'32 GB.',classification:'Verified'},{text:'User says 64 GB.',classification:'User-provided'},{text:'Opinion.',classification:'Inference'},{text:'Not established.',classification:'Unknown'}],sources:[{title:'NVIDIA',kind:'external',url:'https://www.nvidia.com/'},{title:'unsafe',kind:'external',url:'javascript:alert(1)'},{title:'PC status receipt',kind:'tool',url:'sakura://tools/pc-command-status-file-time'}]});
  },source);
  assert.equal(await page.locator('.response-evidence p').count(),5);
  assert.equal(await page.locator('.response-evidence a').count(),1);
  assert.equal(await page.locator('.response-evidence a').getAttribute('href'),'https://www.nvidia.com/');
  assert.match(await page.locator('summary').textContent(),/Verified.*User-provided.*Inference.*Unknown/);
  assert.equal(await page.locator('.response-evidence a').getAttribute('rel'),'noopener noreferrer');
  await page.evaluate(async source=>{
   const {appendEvidence}=await import('data:text/javascript;base64,'+btoa(source));
   const social=document.createElement('div');social.id='social';document.body.append(social);
   appendEvidence(social,{response_kind:'conversation',statements:[{text:'Glad to hear that!',classification:'Inference'}]});
  },source);
  assert.equal(await page.locator('#social .response-evidence').count(),0);
  console.log('PASS: statement provenance, clickable HTTPS citations, unsafe-source rejection');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
