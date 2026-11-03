const {chromium}=require('playwright'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const scratch=await fs.mkdtemp(path.join(os.tmpdir(),'sakura-agent-ui-'));
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
 const draft={id:'action1',tool:'files.write',arguments:{path:'CV-improved.md',content:'A '.repeat(2000)},preview:{path:'CV-improved.md',overwrite:false},reason:'Create the revised draft.',status:'pending'};
 const run={id:'run1',goal:'Improve my CV and save a new draft.',workspace:'C:\\Documents',status:'awaiting_approval',steps:[draft]};
 const state={providers:[{id:'ollama',label:'Configured local model',ready:true}],connections:[],
  tools:[{name:'files.write',inputSchema:{type:'object'}},{name:'shell.run',inputSchema:{type:'object'}}],
  runs:[],skills:[],calendar:{},linkedin:{profile:{}},command_permissions:[{id:'perm1',command:'git status',cwd:'C:\\Documents\\repo'}]};
 const gateways=[{provider:'discord',channels:['read'],users:['42'],enabled:false,running:false,token_set:true,last_error:''},
                 {provider:'slack',channels:[],users:[],enabled:false,running:false,token_set:false,last_error:''},
                 {provider:'whatsapp',channels:[],users:[],enabled:false,running:false,token_set:false,last_error:''}];
 // Whatever the panel proposes becomes the one step the reviewer has to approve.
 function proposed(tool,arguments_,id){const action={id,tool,arguments:arguments_,preview:{warning:'Review the exact target.'},reason:'Prepared from the Agent extension panel.',status:'pending'};run.steps=[action];run.status='awaiting_approval';state.runs=[run];return run;}
 await page.route('http://127.0.0.1/**',async route=>{
  const req=route.request(),u=new URL(req.url());let file;
  if(u.pathname==='/agent')return route.fulfill({contentType:'text/html',body:(await fs.readFile('static/assets/agent.html','utf8')).replace('__AGENT_TOKEN__','test-token')});
  if(u.pathname.startsWith('/static/')){file='.'+u.pathname;return route.fulfill({contentType:file.endsWith('.css')?'text/css':'application/javascript',body:await fs.readFile(file,'utf8')});}
  if(u.pathname==='/api/settings')return route.fulfill({json:{ui_theme:'dark'}});
  const raw=req.postData();
  calls.push({path:u.pathname,method:req.method(),body:raw&&(req.headers()['content-type']||'').includes('json')?JSON.parse(raw):null,token:req.headers()['x-sakura-agent']});
  if(u.pathname==='/api/agent/approval-policy')return route.fulfill({json:{mode:req.method()==='POST'?req.postDataJSON().mode:'ask'}});
  if(u.pathname==='/api/agent/state')return route.fulfill({json:state});
  if(u.pathname==='/api/agent/telegram')return route.fulfill({json:{token_set:false,running:false,enabled:false,chat_ids:[],voice_enabled:false,last_error:''}});
  if(u.pathname==='/api/agent/local-ai')return route.fulfill({json:{models:[],runtime_installed:false,job:{running:false}}});
  if(u.pathname==='/api/agent/gateways')return route.fulfill({json:gateways});
  if(u.pathname.startsWith('/api/agent/gateways/'))return route.fulfill({json:{ok:true}});
  if(u.pathname==='/api/agent/history/search')return route.fulfill({json:{results:[{id:'sess9',goal:'Improve my CV',status:'completed',workspace:'C:\\Documents',created_at:1,snippet:'draft saved'}]}});
  if(u.pathname==='/api/agent/history/sess9')return route.fulfill({json:{id:'sess9',goal:'Improve my CV',status:'completed',archived:true}});
  if(u.pathname==='/api/agent/imports/preview')return route.fulfill({json:{id:'imp1',kind:'skills',warning:'1 reusable procedure, no executable content.',items:[{name:'cv-polish',instructions:'Read the CV, then write a new draft.'}]}});
  if(u.pathname==='/api/agent/imports/imp1/confirm')return route.fulfill({json:{ok:true,imported:1,kind:'skills'}});
  if(u.pathname==='/api/agent/voice/transcribe')return route.fulfill({json:{text:'Read my CV and draft a post.'}});
  if(u.pathname==='/api/agent/permissions/perm1'&&req.method()==='DELETE'){state.command_permissions=[];return route.fulfill({json:{ok:true}});}
  if(u.pathname==='/api/agent/tasks'&&req.method()==='POST'){state.runs=[{...run,steps:[],status:'ready'}];return route.fulfill({json:state.runs[0]});}
  if(u.pathname.endsWith('/delegate'))return route.fulfill({json:proposed('agents.delegate',{goals:req.postDataJSON().goals},'action3')});
  if(u.pathname.endsWith('/propose')){const body=req.postDataJSON();return route.fulfill({json:proposed(body.tool,body.arguments,'action4')});}
  if(u.pathname.endsWith('/decision')){const approve=req.postDataJSON().approve;for(const step of run.steps)step.status=approve?'completed':'rejected';run.status='ready';return route.fulfill({json:{action:run.steps.at(-1),run}});}
  if(u.pathname.endsWith('/plan')){state.runs=[run];return route.fulfill({json:run});}
  if(u.pathname.startsWith('/api/agent/tasks/'))return route.fulfill({json:run});
  return route.fulfill({json:{ok:true}});
 });
 await page.addInitScript(()=>localStorage.setItem('sakura-setup-guide-v1-agent',JSON.stringify({step:0,done:true})));
 await page.goto('http://127.0.0.1/agent');const nav=page.getByRole('navigation',{name:'Agent studio'});
 const go=async label=>{await nav.getByRole('button',{name:label,exact:true}).click();};
 const open=title=>page.locator('summary').filter({hasText:title}).first().click();
 const seen=async(pattern,scope)=>{const box=scope?page.locator(scope).getByText(pattern).first():page.getByText(pattern).first();await box.waitFor();return box.innerText();};
 for(const [name,id]of [['Connections','service-connections'],['Connections','agent-telegram'],['Skills','agent-skills'],['Memory & learning','agent-memory'],['Task history','agent-history'],['Local AI','agent-local-ai'],['Automations','agent-automations'],['Tasks','agent-compose']]){
  await go(name);assert.equal(await page.locator('#'+id).isVisible(),true,name+' view is wired');
 }
 assert.equal(await page.locator('#agent-telegram').isVisible(),false,'Telegram is hidden outside Connections');
 assert.equal(await page.locator('#agent-execution-mode').getAttribute('data-state'),'approval','The panel opens on Approval, matching the header badge');
 assert.equal(await page.locator('header .badge').textContent(),'Local approval required');
 await page.locator('[data-execution-mode="auto"]').click();
 assert.ok(calls.some(c=>c.path==='/api/agent/approval-policy'&&c.body?.mode==='full'&&c.token==='test-token'),'Auto is one choice that also sets the policy');
 assert.equal(await page.locator('#auto-plan').isChecked(),true);
 await page.waitForFunction(()=>document.getElementById('agent-execution-mode').dataset.state==='auto');
 assert.equal(await page.locator('#agent-execution-mode').getAttribute('data-state'),'auto');
 assert.equal(await page.locator('header .badge').textContent(),'Auto: steps run without a click');
 await page.locator('[data-execution-mode="approval"]').click();
 assert.ok(calls.some(c=>c.path==='/api/agent/approval-policy'&&c.body?.mode==='ask'));
 assert.equal(await page.locator('#auto-plan').isChecked(),false);
 await page.fill('#goal','Prepare a task');await page.click('#create');
 assert.equal(await page.locator('#agent-task-options').getAttribute('open'),'');
 assert.equal(await page.locator('#workspace').evaluate(el=>el===document.activeElement),true,'Send guides the user to the missing workspace');
 await page.locator('#agent-task-options>summary').click();
 await page.locator('#agent-access-menu>summary').click();
 await page.locator('[data-approval-mode="balanced"]').click();
 assert.ok(calls.some(c=>c.path==='/api/agent/approval-policy'&&c.body?.mode==='balanced'&&c.token==='test-token'));
 await page.waitForFunction(()=>document.getElementById('agent-access-label').textContent==='Approve for me');
 assert.equal(await page.locator('#agent-execution-mode').getAttribute('data-state'),'custom','A fine-grained policy is shown as neither preset, not silently renamed');
 await page.locator('#agent-task-options>summary').click();
 await page.fill('#goal',run.goal);await page.fill('#workspace','C:\\Documents');
 await page.locator('#agent-task-options>summary').click();await page.click('#create');
 try{await page.locator('#review .reject').waitFor({timeout:8000});}catch(error){console.error('UI errors',errors,'Status',await page.locator('#status').innerText(),'Recent calls',calls.slice(-6));await page.screenshot({path:'F:/AI/assistant/private-model-library-pmx/agent-layout-failure.png'});throw error;}
 assert.ok(calls.some(c=>c.path==='/api/agent/tasks'&&c.body?.goal===run.goal&&c.token==='test-token'));
 for(const viewport of [{width:1440,height:1000},{width:850,height:740},{width:390,height:844}]){
  await page.setViewportSize(viewport);await page.locator('#review .reject').scrollIntoViewIfNeeded();
  for(const cls of ['approve','reject']){const box=await page.locator('#review .'+cls).boundingBox();assert.ok(box&&box.y>=0&&box.y+box.height<=viewport.height,'Approval is visible at '+viewport.width);}
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow at '+viewport.width);
 }
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'F:/AI/assistant/private-model-library-pmx/agent-studio-review.png',fullPage:false});
 await page.click('#review .reject');assert.ok(calls.some(c=>c.path.endsWith('/decision')&&c.body?.approve===false));

 // Terminal backends: the exact command reaches the same authenticated approval path.
 await go('Tasks');await page.locator('#agent-advanced-tools>summary').click();await open('Terminal backends');
 for(const id of ['execution-backend','execution-command'])assert.equal(await page.locator('#'+id).isVisible(),true,id+' is on the tools card');
 await page.selectOption('#execution-backend','docker');assert.equal(await page.locator('#execution-image').isVisible(),true,'Docker asks for an installed digest');
 await page.selectOption('#execution-backend','ssh');assert.equal(await page.locator('#execution-host').isVisible(),true,'SSH asks for the exact host');
 await page.selectOption('#execution-backend','local');
 await page.fill('#execution-command','git status');
 await page.getByRole('button',{name:'Review terminal command'}).click();
 const shellCall=calls.find(c=>c.path.endsWith('/propose')&&c.body?.tool==='shell.run');
 assert.equal(shellCall.body.arguments.command,'git status');assert.equal(shellCall.token,'test-token');
 await page.locator('#remember-command').waitFor();
 assert.equal(await page.locator('#remember-command').isVisible(),true,'A command offers the session allow-list');
 assert.match(await page.locator('#review').innerText(),/Allow this exact command in this folder/,'A remembered local command names its folder');
 await page.selectOption('#execution-backend','ssh');await page.fill('#execution-host','build.example');await page.fill('#execution-user','ci');await page.fill('#execution-remote','/srv');
 await page.getByRole('button',{name:'Review terminal command'}).click();
 await page.locator('#remember-command').waitFor();
 assert.match(await page.locator('#review').innerText(),/on that remote host/,'A remembered SSH command names the machine it reaches');
 assert.ok(calls.some(c=>c.body?.tool==='shell.run'&&c.body.arguments.backend==='ssh'),'The SSH proposal carries its backend');
 await page.check('#remember-command');await page.click('#review .approve');
 assert.ok(calls.some(c=>c.path.endsWith('/decision')&&c.body?.approve===true&&c.body?.remember===true),'Approval carries the allow-list choice');
 await open('Command allow-list');
 assert.match(await page.locator('#command-permissions').innerText(),/git status/,'Saved grant is listed for revoking');
 await page.getByRole('button',{name:'Revoke command permission'}).click();
 assert.ok(calls.some(c=>c.path==='/api/agent/permissions/perm1'&&c.method==='DELETE'));
 assert.match(await seen(/No commands are allow-listed/,'#command-permissions'),/No commands/,'Revoking clears the panel');

 // Parallel delegation and the isolated browser both stop for review first.
 await open('Parallel child tasks');
 assert.equal(await page.locator('#delegate-goals').isVisible(),true,'Delegation goals are editable before review');
 await page.fill('#delegate-goals','audit the dependencies\nsummarise the test failures');
 await page.getByRole('button',{name:'Review parallel delegation'}).click();
 const delegated=calls.find(c=>c.path==='/api/agent/tasks/run1/delegate');
 assert.deepEqual(delegated.body.goals,['audit the dependencies','summarise the test failures']);
 assert.equal(delegated.body.provider,'ollama','Delegation carries the selected planning AI');
 await page.click('#review .reject');
 await open('Isolated browser tools');
 await page.fill('#browser-url','https://example.test');
 await page.getByRole('button',{name:'Review opening page'}).click();
 assert.equal(calls.findLast(c=>c.path.endsWith('/propose')).body.tool,'browser.open');
 await page.click('#review .reject');

 // Slash commands stay in the page: /help creates no task, /search reads the archive.
 const created=calls.filter(c=>c.path==='/api/agent/tasks'&&c.method==='POST').length;
 await page.fill('#goal','/help');await page.click('#create');
 assert.match(await page.locator('#progress').innerText(),/Slash commands:/);
 assert.equal(calls.filter(c=>c.path==='/api/agent/tasks'&&c.method==='POST').length,created,'/help creates no task');
 await page.fill('#goal','/search cv');await page.click('#create');
 assert.equal(await page.inputValue('#history-query'),'cv');
 assert.match(await seen(/matching sessions/,'#history-results'),/1 matching sessions/);
 await page.locator('#history-results button').first().click();
 assert.match(await seen(/Archived session/, '#history-record'),/read only/);

 // Procedure import previews, then confirms through the review-bound endpoint.
 await go('Skills');await open('Import procedures');
 assert.equal(await page.locator('#agent-import-file').isVisible(),true,'Import picker is offered');
 const skill=path.join(scratch,'SKILL.md');await fs.writeFile(skill,'---\nname: cv-polish\n---\nRead the CV, then write a new draft.\n');
 await page.setInputFiles('#agent-import-file',skill);
 await page.getByRole('button',{name:'Approve this import'}).waitFor();
 assert.match(await page.locator('#agent-skills').innerText(),/no executable content/);
 await page.getByRole('button',{name:'Approve this import'}).click();
 assert.match(await seen(/Imported 1 skills/,'#agent-skills'),/Imported 1 skills/);

 // A voice memo transcribes into the goal for review, never straight into an action.
 await go('Tasks');await page.locator('#agent-task-options>summary').click();await open('Transcribe a voice memo');
 assert.equal(await page.locator('#agent-voice-file').isVisible(),true,'Voice memo picker is offered');
 const memo=path.join(scratch,'memo.ogg');await fs.writeFile(memo,'OGGFAKE');
 await page.setInputFiles('#agent-voice-file',memo);
 await page.waitForFunction(()=>document.getElementById('goal').value.includes('Read my CV'));
 assert.equal(await page.inputValue('#goal'),'Read my CV and draft a post.');

 // The other gateways live beside Telegram and post the exact allow lists.
 await go('Connections');
 assert.equal(await page.locator('#agent-other-gateways').isVisible(),true,'Discord/Slack/WhatsApp card is wired');
 assert.equal(await page.locator('#telegram-voice').isVisible(),true,'Telegram voice opt-in is offered');
 await page.selectOption('#gateway-provider','slack');
 assert.match(await seen(/Gateway stopped\./,'#gateway-status'),/Gateway stopped/);
 assert.ok(calls.some(c=>c.path==='/api/agent/gateways'&&c.method==='GET'&&c.token==='test-token'));
 await page.fill('#gateway-channels','general reports');await page.fill('#gateway-users','U1 U2');await page.fill('#gateway-token','xoxb-placeholder');
 await page.getByRole('button',{name:'Save gateway',exact:true}).click();
 const saved=calls.find(c=>c.path==='/api/agent/gateways/slack');
 assert.deepEqual(saved.body.channels,['general','reports']);assert.deepEqual(saved.body.users,['U1','U2']);
 assert.equal(saved.body.token,'xoxb-placeholder');assert.equal(await page.inputValue('#gateway-token'),'','The typed secret leaves the form');
 await page.selectOption('#gateway-provider','whatsapp');
 await page.locator('#gateway-phone').waitFor({state:'visible'});
 await page.locator('#gateway-channels').waitFor({state:'hidden'});
 assert.equal(await page.locator('#gateway-app-secret').isVisible(),true,'WhatsApp needs its own signing secret');

 for(const viewport of [{width:850,height:740},{width:390,height:844}]){
  await go('Tasks');await page.setViewportSize(viewport);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Extension cards add no horizontal overflow at '+viewport.width);
  for(const id of ['execution-command','delegate-goals','browser-url','agent-voice-file']){
   await page.evaluate(name=>document.getElementById(name).scrollIntoView({block:'center'}),id);
   const box=await page.locator('#'+id).boundingBox();
   assert.ok(box&&box.y>=0&&box.y+box.height<=viewport.height,id+' stays reachable at '+viewport.width);
  }
 }
 await page.setViewportSize({width:1440,height:1000});
 await go('Skills');
 await open('Import SKILL.md');
 await page.setInputFiles('#skill-import-file',{name:'SKILL.md',mimeType:'text/markdown',buffer:Buffer.from('---\nname: reviewed-skill\n---\nRead the source and verify the result.')});
 await page.click('#skill-import');
 await page.waitForFunction(()=>document.getElementById('skill-import-file').value==='');
 assert.ok(calls.some(c=>c.path==='/api/agent/skills/import'&&c.body?.markdown.includes('reviewed-skill')&&c.token==='test-token'));
 await open('Local evidence index');
 await page.fill('#knowledge-path','notes.md');await page.click('#knowledge-index');
 await page.waitForFunction(()=>document.getElementById('knowledge-path').value==='notes.md');
 assert.ok(calls.some(c=>c.path.endsWith('/propose')&&c.body?.tool==='knowledge.index'&&c.body.arguments.path==='notes.md'),'Knowledge writes create real pending proposals');
 await go('Tasks');
 await page.screenshot({path:'F:/AI/assistant/private-model-library-pmx/agent-studio-extensions.png',fullPage:false});
 await page.evaluate(()=>{document.documentElement.dataset.uiTheme='light';});
 await go('Tasks');await page.screenshot({path:'F:/AI/assistant/private-model-library-pmx/agent-studio-light.png'});
 await page.evaluate(()=>{document.documentElement.dataset.uiTheme='dark';document.getElementById('agent-task-options').open=false;document.getElementById('agent-advanced-tools').open=false;window.scrollTo(0,0);});
 await page.locator('#agent-access-menu>summary').click();
 await page.screenshot({path:'F:/AI/assistant/private-model-library-pmx/agent-studio-approval-menu.png'});
 assert.deepEqual(errors,[]);
 console.log('PASS: eight Agent views, backend/delegation/browser/voice/import/gateway panels, allow-list grant and revoke, slash commands, authenticated proposals and responsive rendering.');
}finally{await fs.rm(scratch,{recursive:true,force:true});await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
