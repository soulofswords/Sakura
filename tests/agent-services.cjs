const {chromium}=require('playwright'),fs=require('node:fs/promises'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try {
  const page=await browser.newPage(),errors=[],calls=[];
  await page.addInitScript(()=>localStorage.setItem('sakura-setup-guide-v1-agent',JSON.stringify({step:0,done:true})));
  page.setDefaultTimeout(8000);
  page.on('pageerror',error=>errors.push(error.message));
  const state={providers:[{id:'ollama',label:'Local AI',ready:true}],connections:[{id:'nvidia',name:'NVIDIA Broadcast',transport:'http',url:'http://127.0.0.1:18100/gateway'},{id:'legacy-google',name:'Google Calendar',transport:'builtin',service:'google-calendar'}],tools:[],runs:[],skills:[],
   calendar:{configured:true,connected:true,workspace_connected:false},linkedin:{configured:false,connected:false,profile:{}}};
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());calls.push(url.pathname);
   if(url.pathname==='/agent')return route.fulfill({contentType:'text/html',body:(await fs.readFile('static/assets/agent.html','utf8')).replace('__AGENT_TOKEN__','test-token')});
   if(url.pathname.startsWith('/static/js/'))return route.fulfill({contentType:'application/javascript',body:await fs.readFile('.'+url.pathname,'utf8')});
   if(url.pathname==='/static/js/first-run-guide.js')return route.fulfill({contentType:'application/javascript',body:await fs.readFile('static/js/first-run-guide.js','utf8')});
   if(url.pathname==='/static/js/agent-services.js')return route.fulfill({contentType:'application/javascript',body:await fs.readFile('static/js/agent-services.js','utf8')});
   if(url.pathname==='/static/js/agent-workspace.js')return route.fulfill({contentType:'application/javascript',body:await fs.readFile('static/js/agent-workspace.js','utf8')});
   if(url.pathname==='/static/js/agent-memory.js')return route.fulfill({contentType:'application/javascript',body:await fs.readFile('static/js/agent-memory.js','utf8')});
   if(url.pathname==='/static/js/agent-studio.js')return route.fulfill({contentType:'application/javascript',body:await fs.readFile('static/js/agent-studio.js','utf8')});
   if(url.pathname==='/static/css/agent-studio.css')return route.fulfill({contentType:'text/css',body:await fs.readFile('static/css/agent-studio.css','utf8')});
   if(url.pathname==='/api/agent/local-ai')return route.fulfill({json:{models:[],loaded:null,runtime_installed:false,job:{running:false,message:'Ready'}}});
   if(url.pathname==='/api/settings')return route.fulfill({json:{ui_theme:'dark'}});
   if(url.pathname==='/api/agent/state')return route.fulfill({json:state});
   if(url.pathname==='/api/agent/telegram')return route.fulfill({status:503,json:{detail:'Telegram temporarily unavailable'}});
   if(url.pathname==='/api/agent/connections'&&request.method()==='POST'){
    const entry={...request.postDataJSON(),id:'external-google'};state.connections.push(entry);
    return route.fulfill({json:entry});
   }
   if(url.pathname.endsWith('/external-google/discover'))return route.fulfill({json:{id:'discover',tool:'mcp.discover',status:'pending',arguments:{},preview:{server:'Google provider'}}});
   return route.fulfill({json:{ok:true}});
  });
  await page.goto('http://127.0.0.1/agent');
  await page.getByRole('navigation',{name:'Agent studio'}).getByRole('button',{name:'Connections',exact:true}).click();
  await page.locator('#connections').getByText('NVIDIA Broadcast',{exact:true}).waitFor();
  assert.ok((await page.locator('#telegram-state').textContent()).includes('unavailable'),'An optional Telegram failure must not break MCP connections');
  assert.equal(await page.locator('#calendar-connect').isVisible(),false);
  assert.equal(await page.locator('#linkedin-connect').isVisible(),false);
  assert.equal(await page.locator('#service-choice').count(),0,'No built-in service selector.');
  assert.equal(await page.locator('#service-add').count(),0);
  assert.equal(await page.locator('#service-connections').getByRole('heading',{name:'Connections',exact:true}).count(),1);
  assert.equal(await page.locator('#connections').getByText('Google Calendar',{exact:true}).count(),0,'Legacy adapter card stays hidden.');
  const nav=page.getByRole('navigation',{name:'Agent studio'});
  assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),true);
  for(const name of ['Tasks','Local AI','Skills','Memory & learning','Automations','Task history']){
   await nav.getByRole('button',{name,exact:true}).click();
   assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),false,'Schedule must not appear in '+name);
   await page.evaluate(()=>refresh());
   assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),false,'Refreshing account state must not show Schedule in '+name);
  }
  await nav.getByRole('button',{name:'Connections',exact:true}).click();
  assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),true);
  state.calendar.connected=false;await page.evaluate(()=>refresh());
  assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),false,'Disconnected calendar stays hidden');
  await nav.getByRole('button',{name:'Tasks',exact:true}).click();await nav.getByRole('button',{name:'Connections',exact:true}).click();
  assert.equal(await page.locator('#connected-calendar-schedule').isVisible(),false,'Navigation must not show disconnected schedule');
  state.calendar.connected=true;await page.evaluate(()=>refresh());
  await page.getByText('Add MCP server',{exact:true}).click();
  await page.locator('#connection-name').fill('Google provider');
  await page.locator('#mcp-url').fill('https://provider.example/mcp');
  await page.locator('#mcp-token').fill('test-access-token');
  await page.locator('#save-connection').click();
  await page.locator('#connections').getByText('Google provider',{exact:true}).waitFor();
  assert.equal(await page.locator('#mcp-token').inputValue(),'');
  const google=page.locator('#connections .connection').filter({hasText:'Google provider'});
  await google.getByRole('button',{name:'Discover tools',exact:true}).click();
  await page.locator('#review').getByRole('button',{name:'Approve & run',exact:true}).waitFor();
  assert.ok(!calls.some(path=>path.startsWith('/api/agent/services/')));
  assert.equal(await page.locator('#schedule-manager').isVisible(),true,'Schedule remains available outside connection setup.');
  assert.deepEqual(errors,[]);
  console.log('PASS: external MCP-only setup, preserved NVIDIA connection, token clearing and approval-gated discovery.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
