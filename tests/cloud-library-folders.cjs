const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();let finishInstall;
  const models=[{id:'ellen',name:'zenless zone zero / Ellen',format:'pmx',bytes:1200,preview:true},
   {id:'amber',name:'genshin impact / Amber',format:'pmx',bytes:1400,preview:true},
   {id:'astra',name:'zenless zone zero / Astra',format:'pmx',bytes:1800,preview:true},
   {id:'old-kafka',name:'zenless zone zero / Kafka spicy',format:'pmx',bytes:4000,preview:true},
   {id:'kafka-dress',name:'zenless zone zero / Kafka spicy / Dress / Normal',format:'pmx',bytes:2000,preview:true},
   {id:'kafka-glasses',name:'zenless zone zero / Kafka spicy / Dress / Glasses',format:'pmx',bytes:2000,preview:true},
   {id:'haku-office',name:'Miku universe / Haku / Office / Haku',format:'pmx',bytes:2000,preview:true},
   {id:'haku-casual',name:'Miku universe / Haku / Casual / Haku',format:'pmx',bytes:2000,preview:true},
   {id:'gumi',name:'Miku universe / Gumi / Summer / Gumi',format:'pmx',bytes:2000,preview:true}];
  await page.route('http://local.test/**',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:'<div data-studio-content="models"></div><script type="module" src="/library.js"></script>'});
   if(p==='/library.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync('static/js/model-library.js','utf8')});
   if(p.endsWith('/connection'))return route.fulfill({json:{configured:true,url:'https://cloud.test',cloud:'https://cloud.test'}});
   if(p.endsWith('/install')){await new Promise(resolve=>finishInstall=resolve);return route.fulfill({json:{ok:true,models:['pmx/import/Ellen.pmx']}});}
   if(p.endsWith('/preview'))return route.fulfill({status:404,body:''});
   return route.fulfill({json:{models}});
  });
  await page.goto('http://local.test/');
  await page.getByRole('button',{name:'Cloud import PMX',exact:true}).click();
  await page.getByRole('button',{name:'Open game zenless zone zero',exact:true}).waitFor();
  assert.equal(await page.locator('.cloud-character-card').count(),0);
  await page.getByRole('button',{name:'Open game zenless zone zero',exact:true}).click();
  assert.equal(await page.locator('.cloud-character-card').count(),2);
  assert.equal(await page.getByRole('button',{name:'Select zenless zone zero / Kafka spicy',exact:true}).count(),0);
  await page.getByRole('button',{name:'Open folder Kafka spicy',exact:true}).click();
  await page.getByRole('button',{name:'Open folder Dress',exact:true}).click();
  assert.equal(await page.locator('.cloud-character-card').count(),2);
  await page.getByRole('button',{name:'Select zenless zone zero / Kafka spicy / Dress / Glasses',exact:true}).waitFor();
  await page.getByRole('button',{name:'zenless zone zero',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Select genshin impact / Amber',exact:true}).count(),0);
  await page.getByRole('button',{name:'Select zenless zone zero / Ellen',exact:true}).click();
  const ellen=page.locator('.cloud-character-card').filter({has:page.getByRole('button',{name:'Select zenless zone zero / Ellen',exact:true})});
  await ellen.getByRole('button',{name:'Download',exact:true}).click();
  await ellen.locator('progress').waitFor();
  assert.equal(await ellen.getAttribute('aria-busy'),'true');assert.equal(await ellen.locator('.cloud-download-spinner').count(),1);
  finishInstall();await ellen.getByRole('button',{name:'Installed',exact:true}).waitFor();
  assert.equal(await ellen.locator('progress').count(),0);assert.equal(await ellen.getAttribute('aria-busy'),null);
  await page.getByRole('button',{name:'All games',exact:true}).click();
  await page.getByRole('button',{name:'Open game Miku universe',exact:true}).click();
  assert.equal(await page.locator('.cloud-character-card').count(),0);
  assert.equal(await page.locator('.cloud-library-folder').count(),2);
  await page.getByRole('button',{name:'Open folder Haku',exact:true}).click();
  assert.equal(await page.locator('.cloud-character-card').count(),0);
  assert.equal(await page.locator('.cloud-library-folder').count(),2);
  await page.getByRole('button',{name:'Open folder Office',exact:true}).click();
  assert.equal(await page.locator('.cloud-character-card').count(),1);
  await page.locator('[data-library-search]').fill('Summer');
  assert.equal(await page.locator('.cloud-character-card').count(),0);
  await page.getByRole('button',{name:'All games',exact:true}).click();
  await page.locator('[data-library-search]').fill('Amber');
  assert.equal(await page.locator('.cloud-character-card').count(),1);
  await page.getByRole('button',{name:'Select genshin impact / Amber',exact:true}).waitFor();
  console.log('PASS: game folders, character previews, cross-game search and animated download lifecycle.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
